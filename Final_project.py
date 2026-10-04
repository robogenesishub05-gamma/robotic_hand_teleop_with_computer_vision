import cv2
import time
import psutil
import numpy as np 
import math 
import socket 
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision



ESP_IP = "192.168.1.5"
ESP_PORT = 5005

SEND_TO_ESP = True





frame_h = 600

frame_w = 700

base_options = python.BaseOptions(model_asset_path = "hand_landmarker.task")

options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=1,running_mode=vision.RunningMode.VIDEO)

detector = vision.HandLandmarker.create_from_options(options)

mp_drawing = mp.tasks.vision.drawing_utils

mp_hands = mp.tasks.vision.HandLandmarksConnections

mp_drawing_styles = mp.tasks.vision.drawing_styles

angle_joints = [3,6,10,14,18]
tips = [8,12,16,20]

# landmark_look = mp_drawing.DrawingSpec(
#     color=(255, 255, 0),   
#     thickness=5,
#     circle_radius=2
# )

# connections_look = mp_drawing.DrawingSpec(
#     color=(0, 0, 255),  
#     thickness=3
# )

open_values = {3: 155, 6: 142, 10: 140, 14: 150, 18: 152}
closed_values = {3: 145, 6: 133, 10: 122, 14: 138, 18: 140}

pinch_close = {8: 0.030, 12: 0.035, 16: 0.025, 20: 0.030}
pinch_open = {8: 0.055, 12: 0.060, 16: 0.050, 20: 0.055}

angle_min = {3: 115, 6: 95, 10: 90, 14: 95, 18: 95}
angle_max = {3: 180, 6: 175, 10: 165, 14: 177, 18: 172}

def angle_finder(joint,n1,n2):
    v1 = ((n1[0] - joint[0]) , (n1[1] - joint[1]) , (n1[2] - joint[2]))
    v2 = ((n2[0] - joint[0]) , (n2[1] - joint[1]) , (n2[2] - joint[2]))

    dot = (v1[0] * v2[0]) + (v1[1] * v2[1]) + (v1[2] * v2[2])

    m1 = math.sqrt((v1[0] ** 2 ) + (v1[1] ** 2) + (v1[2] ** 2))
    m2 = math.sqrt((v2[0] ** 2 ) + (v2[1] ** 2) + (v2[2] ** 2))

    cos = dot /(m1 * m2)
    cos = max(-1.0, min(1.0, cos))

    rad_angle = math.acos(cos)
    deg_angle = math.degrees(rad_angle)

    return deg_angle


def dist_finder(p1,p2):
    dist = math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2 )
    return dist


def latency_checker(val , close_thresh , open_thresh , current_state):
    if current_state == False and val < close_thresh:
        return True
    elif current_state == True and val > open_thresh:
        return False
    return current_state

def gesture_finder(dict):

    # Open Palm
    if (dict["thumb_bend"] == False and
        dict["index_bend"] == False and
        dict["middle_bend"] == False and
        dict["ring_bend"] == False and
        dict["pinky_bend"] == False and
        dict["index_pinch"] == False):

        return "Open Palm"


    # Fist
    elif (dict["thumb_bend"] == True and
        dict["index_bend"] == True and
        dict["middle_bend"] == True and
        dict["ring_bend"] == True and
        dict["pinky_bend"] == True):

        return "Fist"


    # Point
    elif (dict["thumb_bend"] == True and
        dict["index_bend"] == False and
        dict["middle_bend"] == True and
        dict["ring_bend"] == True and
        dict["pinky_bend"] == True):

        return "Point"


    # Peace
    elif (dict["thumb_bend"] == True and
        dict["index_bend"] == False and
        dict["middle_bend"] == False and
        dict["ring_bend"] == True and
        dict["pinky_bend"] == True):

        return "Peace"

    elif(dict["thumb_bend"] == True and
        dict["index_bend"] == False and
        dict["middle_bend"] == False and
        dict["ring_bend"] == False and
        dict["pinky_bend"] == True):

        return "British Three"

    elif(dict["thumb_bend"] == False and
        dict["index_bend"] == False and
        dict["middle_bend"] == False and
        dict["ring_bend"] == True and
        dict["pinky_bend"] == True):

        return "German Three"

    # Thumbs Up
    elif (dict["thumb_bend"] == False and
        dict["index_bend"] == True and
        dict["middle_bend"] == True and
        dict["ring_bend"] == True and
        dict["pinky_bend"] == True):

        return "Thumbs Up"

    # Middle Finger
    elif (dict["thumb_bend"] == True and
        dict["index_bend"] == True and
        dict["middle_bend"] == False and
        dict["ring_bend"] == True and
        dict["pinky_bend"] == True):

        return "No bad words"


    # rock on 
    elif(dict["thumb_bend"] == True and
        dict["index_bend"] == False and
        dict["middle_bend"] == True and
        dict["ring_bend"] == True and
        dict["pinky_bend"] == False):

        return "Rock On"
    
    # Call
    elif(dict["thumb_bend"] == False and
        dict["index_bend"] == True and
        dict["middle_bend"] == True and
        dict["ring_bend"] == True and
        dict["pinky_bend"] == False):

        return "Call"
    
    # Index Finger Pinch
    elif (dict["index_pinch"] == True):

        return "Pinch/Beautiful"

    else:
        return "Unknown"


def dashboard(frame):

    dashboard_w = 1250
    dashboard_h = 775

    canvas = np.zeros((dashboard_h, dashboard_w, 3), dtype=np.uint8)
    canvas[:] = (35, 35, 35)

    # =========================================================
    # CAMERA
    # =========================================================

    canvas[125 : 125 + frame_h, 0 : frame_w] = frame

    # =========================================================
    # RIGHT PANEL
    # =========================================================

    panel_x = frame_w
    panel_y = 125
    panel_w = dashboard_w - frame_w
    panel_h = frame_h

    cv2.rectangle(
        canvas,
        (panel_x, panel_y),
        (dashboard_w, panel_y + panel_h),
        (45, 45, 45),
        -1
    )

    # =========================================================
    # ANGLE MONITOR
    # =========================================================

    cv2.putText(
        canvas,
        "ANGLE MONITOR",
        (panel_x + 20, panel_y + 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    x_finger = panel_x + 15
    x_raw = panel_x + 130
    x_close = panel_x + 230
    x_open = panel_x + 325
    x_state = panel_x + 430

    header_y = panel_y + 70

    cv2.putText(canvas, "Finger", (x_finger, header_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1)

    cv2.putText(canvas, "RAW", (x_raw, header_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1)

    cv2.putText(canvas, "CLOSE", (x_close, header_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1)

    cv2.putText(canvas, "OPEN", (x_open, header_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1)

    cv2.putText(canvas, "STATE", (x_state, header_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1)

    fingers = [
        ("Thumb", 3),
        ("Index", 6),
        ("Middle", 10),
        ("Ring", 14),
        ("Pinky", 18)
    ]

    y = panel_y + 105

    for name, landmark_id in fingers:

        current = current_angles_raw[landmark_id]
        close_threshold = closed_values[landmark_id]
        open_threshold = open_values[landmark_id]

        state = finger_states[landmark_id]
        state_text = "CLOSED" if state else "OPEN"

        cv2.putText(canvas, name, (x_finger, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1)

        cv2.putText(canvas, f"{current:.0f}", (x_raw, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1)

        cv2.putText(canvas, f"{close_threshold}", (x_close, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1)

        cv2.putText(canvas, f"{open_threshold}", (x_open, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1)

        cv2.putText(canvas, state_text, (x_state, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1)

        y += 30

    # =========================================================
    # THRESHOLD CONTROLS
    # =========================================================

    cv2.line(
        canvas,
        (panel_x + 10, panel_y + 260),
        (dashboard_w - 10, panel_y + 260),
        (80, 80, 80),
        1
    )

    cv2.putText(
        canvas,
        "THRESHOLD CONTROLS",
        (panel_x + 20, panel_y + 290),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    slider_names = [
        ("Thumb Close", 3, closed_values),
        ("Index Close", 6, closed_values),
        ("Middle Close", 10, closed_values),
        ("Ring Close", 14, closed_values),
        ("Pinky Close", 18, closed_values),

        ("Thumb Open", 3, open_values),
        ("Index Open", 6, open_values),
        ("Middle Open", 10, open_values),
        ("Ring Open", 14, open_values),
        ("Pinky Open", 18, open_values)
    ]

    slider_x1 = panel_x + 145
    slider_x2 = panel_x + 500
    slider_start_y = panel_y + 325
    slider_spacing = 25

    for i, (name, landmark_id, value_dict) in enumerate(slider_names):

        slider_y = slider_start_y + i * slider_spacing
        value = value_dict[landmark_id]

        cv2.putText(
            canvas,
            name,
            (panel_x + 15, slider_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (220, 220, 220),
            1,
            cv2.LINE_AA
        )

        # Slider line
        cv2.line(
            canvas,
            (slider_x1, slider_y),
            (slider_x2, slider_y),
            (100, 100, 100),
            4
        )

        # Slider position
        slider_pos = int(
            slider_x1 + (value / 180) * (slider_x2 - slider_x1)
        )

        cv2.circle(
            canvas,
            (slider_pos, slider_y),
            7,
            (0, 255, 255),
            -1
        )

        cv2.putText(
            canvas,
            f"{value}",
            (panel_x + 505, slider_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )

    # =========================================================
    # TOP INFORMATION BAR
    # =========================================================

    cv2.putText(
        canvas,
        f"Gesture: {current_gesture.upper()}",
        (15, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 255, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        canvas,
        f"FPS: {fps:.1f}",
        (15, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        canvas,
        f"CPU: {process_cpu_share:.1f}% | Raw: {process_cpu:.0f}%",
        (180, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        canvas,
        f"RAM: {process_ram:.0f} MB ({process_ram_percent:.1f}%)",
        (500, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        canvas,
        f"PID: {process_pid}",
        (15, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (180, 180, 180),
        1,
        cv2.LINE_AA
    )

    # =========================================================
    # BOTTOM TELEMETRY
    # =========================================================

    telemetry_smoothed = (
        f"T:{int(smoothed_angles[3])} "
        f"I:{int(smoothed_angles[6])} "
        f"M:{int(smoothed_angles[10])} "
        f"R:{int(smoothed_angles[14])} "
        f"P:{int(smoothed_angles[18])}"
    )

    cv2.putText(
        canvas,
        telemetry_smoothed,
        (15, dashboard_h - 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 191, 0),
        2,
        cv2.LINE_AA
    )

    return canvas


def dashboard_mouse(event, x, y, flags, param):

    panel_x = frame_w

    slider_x1 = panel_x + 145
    slider_x2 = panel_x + 500

    slider_start_y = 125 + 325
    slider_spacing = 25

    slider_names = [
        ("Thumb Close", 3, closed_values),
        ("Index Close", 6, closed_values),
        ("Middle Close", 10, closed_values),
        ("Ring Close", 14, closed_values),
        ("Pinky Close", 18, closed_values),

        ("Thumb Open", 3, open_values),
        ("Index Open", 6, open_values),
        ("Middle Open", 10, open_values),
        ("Ring Open", 14, open_values),
        ("Pinky Open", 18, open_values)
    ]

    if event == cv2.EVENT_LBUTTONDOWN or event == cv2.EVENT_MOUSEMOVE:

        if event == cv2.EVENT_MOUSEMOVE and not (flags & cv2.EVENT_FLAG_LBUTTON):
            return

        if slider_x1 <= x <= slider_x2:

            for i, (name, landmark_id, value_dict) in enumerate(slider_names):

                slider_y = slider_start_y + i * slider_spacing

                if abs(y - slider_y) <= 12:

                    value = int(
                        ((x - slider_x1) /
                         (slider_x2 - slider_x1)) * 180
                    )

                    value = max(0, min(180, value))

                    value_dict[landmark_id] = value

                    break

def nothing(z):
    pass


cam = cv2.VideoCapture(1)

cv2.namedWindow("Robot Teleoperation Dashboard", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Robot Teleoperation Dashboard", 1250, 775)

cv2.setMouseCallback(
    "Robot Teleoperation Dashboard",
    dashboard_mouse
)

finger_states = {3: False, 6: False, 10: False, 14: False, 18: False}
pinch_states = {8: False, 12: False, 16: False, 20: False}

signals = {
    "thumb_bend": finger_states[3],
    "index_bend": finger_states[6],
    "middle_bend": finger_states[10],
    "ring_bend": finger_states[14],
    "pinky_bend": finger_states[18],
    "index_pinch": pinch_states[8],
    "middle_pinch": pinch_states[12],
    "ring_pinch": pinch_states[16],
    "pinky_pinch": pinch_states[20],
}

current_gesture = "NO HAND"
current_angles_raw = {3: 0.0, 6: 0.0, 10: 0.0, 14: 0.0, 18: 0.0}
current_angles = {3: 0.0, 6: 0.0, 10: 0.0, 14: 0.0, 18: 0.0}

alpha = 0.2
smoothed_angles = {}
smoothed_init = False


sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 

last_send_time = 0 

fps = 0.0
fps_counter = 0
fps_timer = time.time()

process_cpu = 0.0
process_cpu_share = 0.0
process_ram = 0.0
process_ram_percent = 0.0

performance_timer = time.time()

process = psutil.Process()
process_pid = process.pid



logical_cpus = psutil.cpu_count(logical=True)


process.cpu_percent(None)

while cam.isOpened():
    success , frame = cam.read()



    fps_counter += 1

    current_time = time.time()

    if current_time - fps_timer >= 1.0:

        fps = fps_counter / (current_time - fps_timer)

        fps_counter = 0
        fps_timer = current_time

    if current_time - performance_timer >= 1.0:

        process_cpu = process.cpu_percent(None)

        # Percentage of the entire laptop's CPU capacity
        process_cpu_share = process_cpu / logical_cpus

        process_ram = process.memory_info().rss / (1024 ** 2)

        process_ram_percent = process.memory_percent()

        performance_timer = current_time



    if not success  :
        break

    frame = cv2.resize(frame,(frame_w,frame_h))
    frame = cv2.flip(frame, 1)
    h,w,_ = frame.shape 

    

    rgb_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

    mp_img = mp.Image(mp.ImageFormat.SRGB,rgb_frame)

    timestamp_ms = int(time.time() * 1000)

    result = detector.detect_for_video(mp_img,timestamp_ms)

    if result.hand_world_landmarks:
        for hand_landmarks, hand_world_landmarks in zip(result.hand_landmarks, result.hand_world_landmarks) :
            for landmark_id , landmark in enumerate(hand_world_landmarks):
                if landmark_id in angle_joints:
                    # pixel_x = int(landmark.x*w)
                    # pixel_y = int(landmark.y*h)   

                    j_cords = ((landmark.x) , (landmark.y) , (landmark.z))

                    landmark_n1 = hand_world_landmarks[landmark_id + 1]

                    n1_cords = ((landmark_n1.x) , (landmark_n1.y) , (landmark_n1.z))

                    landmark_n2 = hand_world_landmarks[landmark_id - 1]

                    n2_cords = ((landmark_n2.x) , (landmark_n2.y) , (landmark_n2.z))

                    # ±1 is safe here because 3,6,10,14,18 all sit inside a single finger's block, away from finger boundaries 

                    result_angle =  angle_finder(j_cords,n1_cords,n2_cords)

                    current_angles_raw[landmark_id] = result_angle

                    in_min = angle_min[landmark_id]
                    in_max = angle_max[landmark_id]

                    out_min = 0
                    out_max = 180

                    fraction = (result_angle - in_min) / (in_max - in_min)
                    output = out_min + fraction * (out_max - out_min)
                    output = max(0, min(180, output))

                    current_angles[landmark_id] = output

                    if not smoothed_init:
                        smoothed_angles[landmark_id] = output
                    else :
                        smoothed_angles[landmark_id] = alpha * output + (1-alpha) * smoothed_angles[landmark_id]

                    finger_states[landmark_id] = latency_checker(result_angle, closed_values[landmark_id], open_values[landmark_id], finger_states[landmark_id])

            smoothed_init = True 

            thumb_tip = (hand_world_landmarks[4].x, hand_world_landmarks[4].y, hand_world_landmarks[4].z)

            for tip_id in tips:
                tip_point = (hand_world_landmarks[tip_id].x, hand_world_landmarks[tip_id].y, hand_world_landmarks[tip_id].z)
                distance = dist_finder(thumb_tip,tip_point)
                pinch_states[tip_id] = latency_checker(distance, pinch_close[tip_id], pinch_open[tip_id], pinch_states[tip_id])



            signals = {
                "thumb_bend": finger_states[3],
                "index_bend": finger_states[6],
                "middle_bend": finger_states[10],
                "ring_bend": finger_states[14],
                "pinky_bend": finger_states[18],
                "index_pinch": pinch_states[8],
                "middle_pinch": pinch_states[12],
                "ring_pinch": pinch_states[16],
                "pinky_pinch": pinch_states[20],
            }

            current_gesture = gesture_finder(signals)


            mp_drawing.draw_landmarks(frame, hand_landmarks,mp_hands.HAND_CONNECTIONS,mp_drawing_styles.get_default_hand_landmarks_style(),mp_drawing_styles.get_default_hand_connections_style())

            # mp_drawing.draw_landmarks(frame, hand_landmarks,mp_hands.HAND_CONNECTIONS, landmark_look, connections_look )

    else :
        print("No Hand Detected")
        current_gesture = "NO HAND"
        current_angles_raw = {3: 180.0, 6: 180.0, 10: 180.0, 14: 180.0, 18: 180.0}
        current_angles = {3: 180.0, 6: 180.0, 10: 180.0, 14: 180.0, 18: 180.0}
        smoothed_angles = {3: 180.0, 6: 180.0, 10: 180.0, 14: 180.0, 18: 180.0}
        smoothed_init = False

    msg = f"{smoothed_angles[3]:.1f},{smoothed_angles[6]:.1f},{smoothed_angles[10]:.1f},{smoothed_angles[14]:.1f},{smoothed_angles[18]:.1f}"

    if time.time() - last_send_time >= 1/30:
        last_send_time = time.time()
        if SEND_TO_ESP :
            byte_msg = msg.encode()

            sender_socket.sendto(byte_msg,(ESP_IP , ESP_PORT))

        else : 
            print(f"The following message would have been sent to the ESP : {msg}")
            print(f"Thumb:{signals['thumb_bend']} Index:{signals['index_bend']} Middle:{signals['middle_bend']} Ring:{signals['ring_bend']} Pinky:{signals['pinky_bend']} | Idx-Pinch:{signals['index_pinch']} Mid-Pinch:{signals['middle_pinch']} Ring-Pinch:{signals['ring_pinch']} Pnk-Pinch:{signals['pinky_pinch']} Gesture:{current_gesture}")


    canvas = dashboard(frame)

    cv2.imshow(
        "Robot Teleoperation Dashboard",
        canvas
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
    


    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


sender_socket.close()
cam.release()
cv2.destroyAllWindows()