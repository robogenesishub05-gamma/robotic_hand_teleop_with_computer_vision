# Technical Documentation — Robotic Hand Teleoperation

This document covers how the system works internally: the data flow, the maths behind each stage, the network protocol, the firmware, and how to tune it. For setup steps see the [README](../README.md).

## Contents

1. [System overview](#1-system-overview)
2. [Hand tracking](#2-hand-tracking)
3. [Joint angle calculation](#3-joint-angle-calculation)
4. [Angle-to-servo mapping](#4-angle-to-servo-mapping)
5. [Smoothing](#5-smoothing)
6. [Finger state and hysteresis](#6-finger-state-and-hysteresis)
7. [Pinch detection](#7-pinch-detection)
8. [Gesture classification](#8-gesture-classification)
9. [Communication protocol](#9-communication-protocol)
10. [ESP32 firmware](#10-esp32-firmware)
11. [Dashboard](#11-dashboard)
12. [Configuration reference](#12-configuration-reference)
13. [Fail-safe behaviour](#13-fail-safe-behaviour)
14. [Troubleshooting](#14-troubleshooting)
15. [Design decisions](#15-design-decisions)
16. [Known issues](#16-known-issues)

---

## 1. System overview

The system is split into two programs connected by Wi-Fi.

| | Laptop (`Final_project.py`) | ESP32 (`main.py`) |
|---|---|---|
| Language | Python 3.11 | MicroPython |
| Job | Perception and decision-making | Actuation |
| Inputs | Webcam frames | UDP packets |
| Outputs | UDP packets, dashboard | 5 PWM signals |

All the heavy work stays on the laptop. The ESP32 only parses five numbers and writes five duty cycles, which keeps the firmware small and the control loop on the microcontroller fast.

Per frame, the laptop does:

1. Capture a frame, resize to 640×480, mirror it horizontally.
2. Convert BGR → RGB and wrap it in an `mp.Image`.
3. Run `HandLandmarker.detect_for_video()`.
4. For each of the five tracked joints: compute the joint angle, map it to a servo angle, smooth it, update the open/closed state.
5. Compute four thumb-to-fingertip distances and update pinch states.
6. Classify the gesture from the nine boolean signals.
7. If at least 1/30 s has passed since the last packet, send the five smoothed angles to the ESP32.
8. Draw the dashboard.

## 2. Hand tracking

The model is MediaPipe's `hand_landmarker.task`, loaded through the Tasks API:

```python
options = vision.HandLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path="hand_landmarker.task"),
    num_hands=1,
    running_mode=vision.RunningMode.VIDEO,
)
```

`VIDEO` mode is used rather than `IMAGE` because it lets MediaPipe track the hand between frames instead of re-detecting it from scratch every time. That's faster and much more stable. It requires a monotonically increasing timestamp, which comes from `time.time()` in milliseconds.

The result gives two sets of 21 landmarks:

- `hand_landmarks`: normalised image coordinates (x, y in 0–1, z relative to the wrist). Only used for drawing the skeleton on the frame.
- `hand_world_landmarks`: real-world 3D coordinates in metres, centred on the hand. **All calculations use these.**

### Landmark indices used

```
        8   12  16  20        tips
        7   11  15  19
   4    6   10  14  18        ◄─ joints measured (3 for thumb)
   3    5    9  13  17
   2
   1
            0                 wrist
```

| Finger | Joint measured | Neighbours used |
|---|---|---|
| Thumb | 3 (IP) | 2 and 4 |
| Index | 6 (PIP) | 5 and 7 |
| Middle | 10 (PIP) | 9 and 11 |
| Ring | 14 (PIP) | 13 and 15 |
| Pinky | 18 (PIP) | 17 and 19 |

These are the ids in `angle_joints = [3, 6, 10, 14, 18]`. Each joint's neighbours are always `id - 1` and `id + 1`, which is why the loop can compute them generically. The PIP joint was picked because it's the one that moves the most when you curl a finger, so it gives the cleanest signal.

## 3. Joint angle calculation

`angle_finder(joint, n1, n2)` returns the angle at `joint` between the bones going to `n1` and `n2`.

Build two vectors that start at the joint:

```
v1 = n1 − joint
v2 = n2 − joint
```

Then use the dot product:

```
v1 · v2 = |v1| |v2| cos θ

θ = arccos( (v1 · v2) / (|v1| |v2|) )
```

A straight finger gives roughly 180° (the two bones point in opposite directions). A fully curled finger gives something around 90°.

Before calling `acos`, the cosine is clamped to [-1, 1]. Floating-point error can push it to 1.0000001, and `math.acos` throws on anything outside that range.

Because the vectors are 3D and in metres, the angle doesn't change when the hand moves towards or away from the camera, and it's mostly unaffected by rotating the hand. A 2D version (`angle_finder_thumb`) exists from an earlier experiment with the thumb but isn't used.

## 4. Angle-to-servo mapping

Real joints never reach a full 0–180° range, so the measured angle is stretched linearly between a per-finger calibrated "closed" and "open" angle:

```
fraction = (raw − angle_closed) / (angle_open − angle_closed)
servo    = clamp(fraction × 180, 0, 180)
```

Current calibration:

| Finger | `angle_closed` | `angle_open` |
|---|---|---|
| Thumb | 115° | 158° |
| Index | 93° | 171° |
| Middle | 88° | 144° |
| Ring | 93° | 161° |
| Pinky | 101° | 166° |

So **0 = finger fully closed, 180 = fully open**. The firmware treats 180 as the rest position, so the hand starts open.

Clamping matters: overshooting the calibrated range (which happens often) would otherwise send values beyond what the servo or the printed hand can physically do.

## 5. Smoothing

Landmarks wobble by a few millimetres frame to frame. Sent straight to the servos, this shows up as constant buzzing. Each servo angle goes through an exponential moving average:

```
smoothed = α · new + (1 − α) · smoothed_prev        α = 0.3
```

With α = 0.3, each new frame contributes 30% and history contributes 70%. That removes most of the jitter while still reaching ~95% of a sudden change in about 8 frames (roughly a quarter of a second at 30 FPS).

- Higher α → snappier, more jitter.
- Lower α → smoother, more lag.

The filter is re-seeded with the current mapped servo value (`smoothed_init`) the first time a hand appears, so the servos don't slowly crawl in from the last known position.

## 6. Finger state and hysteresis

For gestures we need a yes/no answer per finger: is it bent? A single threshold doesn't work because a finger resting near that threshold flips between open and closed every frame.

`latency_checker()` uses two thresholds instead:

```python
def latency_checker(val, close_thresh, open_thresh, current_state):
    if current_state == False and val < close_thresh:
        return True        # was open, now clearly closed
    elif current_state == True and val > open_thresh:
        return False       # was closed, now clearly open
    return current_state   # in the dead band: keep the last state
```

```
angle  ─────────────────────────────────────────►
       CLOSED   │ close_thresh   dead band   open_thresh │   OPEN
                ▲─────── state never changes here ───────▲
```

Default thresholds (draggable at runtime from the dashboard):

| Finger | Close below | Open above |
|---|---|---|
| Thumb | 145° | 155° |
| Index | 133° | 142° |
| Middle | 122° | 140° |
| Ring | 138° | 150° |
| Pinky | 140° | 152° |

These thresholds are separate from the servo calibration in §4. They only decide the boolean state used for gestures. The servos always get the continuous angle.

## 7. Pinch detection

A pinch is the thumb tip (landmark 4) touching another fingertip (8, 12, 16 or 20). It's the 3D Euclidean distance between them:

```
d = √((x₁−x₂)² + (y₁−y₂)² + (z₁−z₂)²)
```

Since world landmarks are in metres, the thresholds are physical distances and don't depend on how far the hand is from the camera. The same hysteresis function from §6 applies:

| Fingertip | Pinch below | Release above |
|---|---|---|
| Index | 3.0 cm | 5.5 cm |
| Middle | 3.5 cm | 6.0 cm |
| Ring | 2.5 cm | 5.0 cm |
| Pinky | 3.0 cm | 5.5 cm |

All four are tracked. Only the index pinch is used by the classifier right now.

## 8. Gesture classification

`gesture_finder()` takes nine booleans (five `*_bend`, four `*_pinch`) and matches them against fixed patterns. `B` = bent, `·` = straight.

| Gesture | Thumb | Index | Middle | Ring | Pinky |
|---|---|---|---|---|---|
| Open Palm | · | · | · | · | · |
| Fist | B | B | B | B | B |
| Point | B | · | B | B | B |
| Peace | B | · | · | B | B |
| British Three | B | · | · | · | B |
| German Three | · | · | · | B | B |
| Thumbs Up | · | B | B | B | B |
| Middle finger (`"No bad words"`) | B | B | · | B | B |
| Rock On | B | · | B | B | · |
| Call | · | B | B | B | · |

**Pinch** is reported when the thumb tip touches the index tip and none of the patterns above matched. Open Palm additionally requires no index pinch. Patterns are checked top to bottom and the first match wins. Anything that doesn't match is reported as `Unknown`.

A lookup-style rule set was chosen over a trained classifier on purpose: it needs no dataset, it's easy to debug from the dashboard, and adding a gesture is one `elif`. The trade-off is that it only knows what you explicitly wrote down.

## 9. Communication protocol

| | |
|---|---|
| Transport | UDP over Wi-Fi |
| Port | 5005 |
| Rate | Capped at 30 packets/s |
| Encoding | ASCII |
| Format | `thumb,index,middle,ring,pinky` |

Example packet:

```
142.3,180.0,175.6,12.4,0.0
```

Five floats with one decimal place, in the range 0–180, comma-separated, no trailing newline.

**Why UDP and not TCP:** in teleoperation, a late packet is useless. If one gets lost, the next one is only 33 ms behind and carries the newer position anyway. TCP would retransmit the stale value and block newer ones behind it, which shows up as stutter. UDP also needs no connection setup, so the laptop and ESP32 can be started in any order.

The send rate is limited independently of the camera's FPS, so a fast camera doesn't flood the ESP32's receive buffer.

## 10. ESP32 firmware

`main.py` runs on boot.

**Startup**

1. Configure five PWM channels at 50 Hz on GPIO 13, 12, 14, 27, 26.
2. Move all servos to 180 (hand open).
3. Connect to Wi-Fi, with a 10 s timeout (20 × 0.5 s).
4. Blink the onboard LED (GPIO 2): once for connected, twice for failed.
5. If connected, bind a UDP socket on `0.0.0.0:5005` with a 2 s receive timeout.

**Main loop**

```
receive packet
  ├─ 5 valid numbers → write each servo's duty cycle
  ├─ wrong field count → log "malformed packet", ignore
  └─ any socket OSError (normally the 2 s timeout) → open hand, blink LED 3×
```

A packet with five fields where one isn't a number (e.g. `a,1,2,3,4`) raises `ValueError` in `parse_angles()`. That isn't caught, so the loop stops and the board needs a reset (see §16).

**Angle to PWM.** Hobby servos expect a pulse every 20 ms (50 Hz). The pulse width sets the position:

```
pulse_ms = 0.5 + (angle / 180) × 2.0        → 0.5 ms at 0°, 2.5 ms at 180°
duty_u16 = (pulse_ms / 20) × 65535
```

`duty_u16` is MicroPython's 16-bit duty-cycle API, so 65535 = 100%. A 1.5 ms pulse (centre) works out to about 4915.

The 0.5–2.5 ms range suits most SG90/MG90S servos. Some servos only accept 1–2 ms. If one buzzes or strains at the ends of its travel, narrow the range in `duty_cycle_value()`.

## 11. Dashboard

The main branch draws everything with OpenCV onto a single 1250×775 canvas:

- **Top-left:** current gesture, FPS, process CPU (raw and divided by logical core count), RAM in MB and as a %, PID
- **Left:** mirrored camera feed with the MediaPipe skeleton drawn on
- **Right, top:** angle monitor: raw angle, close/open thresholds and current state per finger
- **Right, bottom:** ten sliders for the close/open thresholds. Click or drag to change them live.
- **Bottom:** smoothed servo values about to be sent (`T: I: M: R: P:`)

Sliders are implemented by hand: `dashboard_mouse()` is registered with `cv2.setMouseCallback`, checks whether the click is within 12 px of a slider's row, and converts the x position to 0–180.

The `ui` branch replaces this with a CustomTkinter window. It has the same information plus a smoothed-angle column, and uses real slider widgets. Note that `ui` branched off before the calibration changes on `main`: it still uses the `angle_min` / `angle_max` mapping, `alpha = 0.2`, a 700×600 frame, camera index 1 and `ESP_IP = 192.168.1.5`, and has no `safe_position`.

## 12. Configuration reference

All in `Final_project.py`, near the top.

| Name | Default | Purpose |
|---|---|---|
| `ESP_IP` | `192.168.1.2` | ESP32 address |
| `ESP_PORT` | `5005` | UDP port, must match `PORT` in `main.py` |
| `SEND_TO_ESP` | `True` | `False` prints packets instead of sending |
| `frame_w`, `frame_h` | 640, 480 | Processing resolution |
| `angle_open`, `angle_closed` | per finger | Servo mapping calibration (§4) |
| `open_values`, `closed_values` | per finger | Bend-state hysteresis (§6) |
| `pinch_close`, `pinch_open` | per fingertip | Pinch hysteresis, metres (§7) |
| `alpha` | 0.3 | EMA smoothing factor (§5) |
| `safe_position` | all 180 | Servo values sent when no hand is visible |
| `cv2.VideoCapture(0)` | camera 0 | Webcam index |

In `main.py`:

| Name | Purpose |
|---|---|
| `WIFI_NAME`, `WIFI_PASSWORD` | Network credentials |
| `PORT` | UDP listen port |
| servo pin list | GPIO for each finger |

## 13. Fail-safe behaviour

Two independent layers return the hand to a known, relaxed position:

1. **Laptop side:** if no hand is detected, the program sends 180 for every finger and resets the smoothing filter.
2. **ESP32 side:** if no packet arrives for 2 s (laptop closed, crashed, or out of Wi-Fi range), the socket times out and the firmware opens the hand and blinks the LED three times. It keeps listening and resumes as soon as packets come back.

The open position is used as the safe state because it puts no load on the tendons or servos.

## 14. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Black window or `cam.isOpened()` false | Wrong camera index. Try `VideoCapture(1)` (or another index) if the default camera isn't the one you want. |
| `RuntimeError` loading the model | `hand_landmarker.task` isn't in the working directory. |
| Servos don't move, dashboard works | Check `ESP_IP` matches the IP printed on the ESP32 serial console. Both devices must be on the same network. Run with `SEND_TO_ESP = False` to confirm packets are being generated. |
| ESP32 LED blinks 3× repeatedly | No packets are arriving. Same checks as above, plus check the Windows firewall isn't blocking outbound UDP from Python. |
| ESP32 resets when servos move | Servos are pulling too much current from the board. Use a separate 5 V supply with common ground. |
| Servos jitter at rest | Lower `alpha`, or check the servo supply. Jitter at rest is often electrical, not software. |
| A finger never registers as bent | Its `closed_values` threshold is too low. Watch RAW while making a fist and set it a few degrees above that. |
| Finger moves backwards | Servo horn mounted the other way. Easiest fix is to use `180 - angle` for that finger in the firmware. |
| Low FPS | Close other camera apps. CPU usage is shown on the dashboard. MediaPipe on CPU should manage 25–30 FPS on most laptops. |

## 15. Design decisions

**MediaPipe for tracking only.** The landmark model solves the hard computer vision problem (finding a hand and its 21 keypoints). Everything after that is plain geometry, and writing it myself means every stage can be inspected and tuned individually, which made debugging the hand far easier than a black-box gesture model would have.

**World landmarks instead of image landmarks.** Image coordinates are distorted by perspective and depend on distance from the camera. World landmarks are metric 3D, so angles and pinch distances mean the same thing wherever the hand is.

**Two separate threshold sets.** Servo motion needs a continuous value; gestures need a clean boolean. Mixing them would force a compromise on both, so the calibrated range (§4) and the hysteresis thresholds (§6) are kept independent.

**Computation on the laptop.** The ESP32 would struggle to run the landmark model. Keeping it as a "dumb" actuator also means the vision code can change without reflashing the board.

## 16. Known issues

- `print("RAW: ...")` runs for every joint on every frame, which slows the loop slightly and floods the console. It should be behind a debug flag.
- `angle_min`, `angle_max`, `servo_closed`, `servo_open`, `angle_finder_thumb()` and `nothing()` are left over from earlier experiments and are unused.
- In `main.py`, a five-field packet containing a non-number crashes the receive loop (`ValueError` from `float()` isn't caught). Catching `ValueError` alongside the malformed-packet case would fix it.
- Threshold changes made with the sliders are lost when the program exits.
- Wi-Fi credentials are hard-coded in `main.py`. They should be moved to a separate file that's listed in `.gitignore`.
- Only the thumb's IP joint is measured, so thumb abduction/opposition isn't reproduced.
