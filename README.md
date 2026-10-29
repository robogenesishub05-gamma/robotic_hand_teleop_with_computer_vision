# Robotic Hand Teleoperation with Computer Vision

Control a 5-servo robotic hand with your own hand, using nothing but a webcam.

The laptop tracks your hand with MediaPipe, works out how bent each finger is, recognises a small set of gestures, and streams servo angles to an ESP32 over Wi-Fi. The ESP32 drives one servo per finger, so the robotic hand mirrors yours in real time.

MediaPipe is used **only** for hand tracking (the 21 landmarks). Joint-angle math, open/closed detection, pinch detection, gesture classification, smoothing and the angle-to-servo mapping are all written from scratch in this repo. The built-in MediaPipe Gesture Recognizer is not used.

---

## How it works

```
 webcam ──► OpenCV ──► MediaPipe Hand Landmarker ──► 21 world landmarks (metres)
                                                          │
                       ┌──────────────────────────────────┤
                       ▼                                  ▼
            joint angle per finger              thumb-tip ↔ fingertip distance
            (dot product, 3D vectors)                     │
                       │                                  ▼
          ┌────────────┴───────────┐               pinch detection
          ▼                        ▼               (with hysteresis)
   normalise to 0–180°     open / closed state            │
   + EMA smoothing         (with hysteresis)  ────────────┤
          │                                               ▼
          │                                      rule-based gesture
          ▼                                         classifier
   "T,I,M,R,P" over UDP @ 30 Hz                          │
          │                                               ▼
          ▼                                        dashboard overlay
   ESP32 (MicroPython) ──► 50 Hz PWM ──► 5 servos
```

## Features

- Real-time single-hand tracking with the MediaPipe Tasks `HandLandmarker` (video mode)
- Finger flexion measured from 3D world landmarks, so it holds up when the hand moves closer or further from the camera
- Hysteresis on every open/closed and pinch decision, so states don't flicker at the boundary
- Exponential moving average on servo angles to remove jitter before it reaches the motors
- 11 recognised gestures: Open Palm, Fist, Point, Peace, Thumbs Up, Rock On, Call, British Three, German Three, Pinch (shown as "Pinch/Beautiful"), and one rude one
- Live dashboard: camera feed, raw angles, per-finger state, FPS, process CPU and RAM
- Threshold sliders you can drag while the program is running, which makes calibration quick
- Fail-safe on both ends: the hand opens fully if tracking is lost, or if the ESP32 stops receiving packets for 2 s

## Hardware

| Part | Notes |
|---|---|
| ESP32 dev board | Flashed with MicroPython |
| 5 × hobby servos (SG90 / MG90S) | One per finger |
| Tendon-driven robotic hand | 3D printed |
| External 5 V supply | Servos must **not** be powered from the ESP32's 3.3 V/5 V pins |
| Webcam | Built-in or USB |

Servo signal pins on the ESP32:

| Finger | GPIO |
|---|---|
| Thumb | 13 |
| Index | 12 |
| Middle | 14 |
| Ring | 27 |
| Pinky | 26 |

Tie the servo supply ground to the ESP32 ground.

## Repository layout

```
Final_project.py        main teleoperation program (laptop side)
main.py                 MicroPython firmware for the ESP32 (hardware side)
hand_landmarker.task    MediaPipe hand landmark model
landmark_reader.py      minimal script that prints raw landmarks, handy for debugging
docs/DOCUMENTATION.md   full technical write-up
```

The `ui` branch has an alternative front-end built with CustomTkinter (proper widgets and sliders instead of the OpenCV-drawn dashboard). It branched off before the latest calibration changes, so its pipeline is older than `main`'s: it still maps angles with `angle_min` / `angle_max`, uses `alpha = 0.2`, a 700×600 frame and camera index 1, and has its own `ESP_IP`.

## Getting started

### 1. Laptop

Python 3.11 is what this was developed on.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install mediapipe opencv-python numpy psutil
# only needed for the ui branch:
pip install customtkinter pillow
```

`hand_landmarker.task` is already in the repo. If it's missing, download it from the MediaPipe Hand Landmarker model page and put it next to `Final_project.py`.

### 2. ESP32

1. Flash MicroPython onto the board.
2. Open `main.py` and set `WIFI_NAME` / `WIFI_PASSWORD` for your network.
3. Upload it to the board as `main.py` (Thonny works fine) and reset.
4. The serial console prints the IP the board got. The onboard LED blinks once if Wi-Fi connected, twice if it didn't.

### 3. Point the laptop at the ESP32

At the top of `Final_project.py`:

```python
ESP_IP = "192.168.1.2"     # the IP printed by the ESP32
ESP_PORT = 5005
SEND_TO_ESP = True         # False = dry run, prints packets instead of sending
```

Also check the camera index: `cv2.VideoCapture(0)` uses the default (usually built-in) webcam. Change it to `1` for a second / USB camera.

### 4. Run

```bash
python Final_project.py
```

Hold one hand up to the camera. Press `q` to quit.

## Calibration

Everyone's hand (and camera angle) is a bit different, so expect to tune a few numbers the first time:

1. Run with `SEND_TO_ESP = False`.
2. Fully open and then fully close your hand and watch the **RAW** column in the dashboard.
3. Put those values into `angle_open` / `angle_closed`. They set the range that gets stretched to 0–180° for the servos.
4. Drag the **Close/Open** sliders until each finger's state switches cleanly. These are the hysteresis thresholds and they only affect gesture detection, not servo motion.

More detail, including the maths, is in [`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md).

## Known limitations

- One hand only (`num_hands=1`).
- The thumb is measured at a single joint (IP), so thumb opposition isn't captured.
- The link is one-way: the ESP32 never replies, so the laptop can’t tell if the robot is connected or how many packets are lost. It also accepts packets from any device on the network.
- Wi-Fi credentials and the ESP32 IP are hard-coded for now.

## Roadmap/Future implementation plans

- Thumb CMC/MCP angle for better thumb motion
- Record and replay gesture sequences
- Per-user calibration saved to disk

## Author

Varad S. Patil
