import cv2
import time
import psutil
import numpy as np 
import math 
import socket 
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import customtkinter as ctk
from PIL import Image, ImageTk

print("[DEBUG] Python program started")
print("[DEBUG] Imports completed")


ESP_IP = "192.168.1.5"
ESP_PORT = 5005

SEND_TO_ESP = True



debug_stage = 0

frame_h = 600

frame_w = 700

print("[DEBUG] Loading MediaPipe model...")


base_options = python.BaseOptions(model_asset_path = "hand_landmarker.task")

options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=1,running_mode=vision.RunningMode.VIDEO)

detector = vision.HandLandmarker.create_from_options(options)

print("[DEBUG] MediaPipe model loaded successfully")

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




print("[DEBUG] Starting camera...")

cam = cv2.VideoCapture(1)

if cam.isOpened():
    print("[DEBUG] Camera opened successfully")
else:
    print("[DEBUG] ERROR: Camera failed to open")


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

print("[DEBUG] Creating CustomTkinter window...")

root = ctk.CTk()
root.title("Robot Teleoperation")

print("[DEBUG] CustomTkinter window created")

root.geometry("1250x775")

running = True

def quit_program(event=None):
    global running
    print("[DEBUG] Q pressed - exiting...")
    running = False

root.bind("<q>", quit_program)




root.grid_columnconfigure(0, weight=7)
root.grid_columnconfigure(1, weight=5)
root.grid_rowconfigure(1, weight=1)

# =========================
# USER INTERFACE
# =========================

root.grid_columnconfigure(0, weight=7)
root.grid_columnconfigure(1, weight=5)
root.grid_rowconfigure(1, weight=1)

# =========================
# HEADER
# =========================

header = ctk.CTkFrame(root)
header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))

title_label = ctk.CTkLabel(header, text="ROBOT TELEOPERATION", font=ctk.CTkFont(size=22, weight="bold"))
title_label.grid(row=0, column=0, columnspan=4, pady=(10, 5))

gesture_label = ctk.CTkLabel(header, text="Gesture: NO HAND", font=ctk.CTkFont(size=14, weight="bold"))
gesture_label.grid(row=1, column=0, padx=20, pady=(0, 10))

fps_label = ctk.CTkLabel(header, text="FPS: 0.0", font=ctk.CTkFont(size=14))
fps_label.grid(row=1, column=1, padx=20)

cpu_label = ctk.CTkLabel(header, text="CPU: 0.0%", font=ctk.CTkFont(size=14))
cpu_label.grid(row=1, column=2, padx=20)

ram_label = ctk.CTkLabel(header, text="RAM: 0 MB", font=ctk.CTkFont(size=14))
ram_label.grid(row=1, column=3, padx=20)


# =========================
# CAMERA
# =========================

camera_frame = ctk.CTkFrame(root)
camera_frame.grid(row=1, column=0, padx=(8, 4), pady=8, sticky="nsew")

camera_frame.grid_rowconfigure(0, weight=1)
camera_frame.grid_columnconfigure(0, weight=1)

camera_label = ctk.CTkLabel(camera_frame, text="Starting camera...")
camera_label.grid(row=0, column=0, sticky="nsew")


# =========================
# RIGHT PANEL
# =========================

right_panel = ctk.CTkFrame(root)
right_panel.grid(row=1, column=1, padx=(4, 8), pady=8, sticky="nsew")

right_panel.grid_columnconfigure(0, weight=1)


# =========================
# FINGER MONITOR
# =========================

ctk.CTkLabel(right_panel, text="FINGER MONITOR", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=15, pady=(12, 8), sticky="w")

monitor_frame = ctk.CTkFrame(right_panel)
monitor_frame.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")

monitor_frame.grid_columnconfigure(0, weight=2)
monitor_frame.grid_columnconfigure(1, weight=1)
monitor_frame.grid_columnconfigure(2, weight=1)
monitor_frame.grid_columnconfigure(3, weight=1)

ctk.CTkLabel(monitor_frame, text="FINGER", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=8, pady=6)
ctk.CTkLabel(monitor_frame, text="RAW", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=8)
ctk.CTkLabel(monitor_frame, text="SMOOTH", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=8)
ctk.CTkLabel(monitor_frame, text="STATE", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, padx=8)

finger_labels = {}

for row_index, (name, landmark_id) in enumerate([("Thumb", 3), ("Index", 6), ("Middle", 10), ("Ring", 14), ("Pinky", 18)], start=1):

    ctk.CTkLabel(monitor_frame, text=name, anchor="w").grid(row=row_index, column=0, padx=8, pady=5, sticky="w")

    raw_label = ctk.CTkLabel(monitor_frame, text="180°")
    raw_label.grid(row=row_index, column=1, padx=8)

    smooth_label = ctk.CTkLabel(monitor_frame, text="180°")
    smooth_label.grid(row=row_index, column=2, padx=8)

    state_label = ctk.CTkLabel(monitor_frame, text="OPEN")
    state_label.grid(row=row_index, column=3, padx=8)

    finger_labels[landmark_id] = {
        "angle": raw_label,
        "smooth": smooth_label,
        "state": state_label
    }


# =========================
# CALIBRATION
# =========================

ctk.CTkLabel(right_panel, text="CALIBRATION", font=ctk.CTkFont(size=18, weight="bold")).grid(row=2, column=0, padx=15, pady=(5, 8), sticky="w")

calibration_frame = ctk.CTkFrame(right_panel)
calibration_frame.grid(row=3, column=0, padx=12, pady=(0, 10), sticky="ew")

calibration_frame.grid_columnconfigure(0, weight=1)
calibration_frame.grid_columnconfigure(1, weight=4)
calibration_frame.grid_columnconfigure(2, weight=1)
calibration_frame.grid_columnconfigure(3, weight=4)
calibration_frame.grid_columnconfigure(4, weight=1)

ctk.CTkLabel(calibration_frame, text="FINGER", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=6)

ctk.CTkLabel(calibration_frame, text="CLOSE", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5)
ctk.CTkLabel(calibration_frame, text="°", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2)

ctk.CTkLabel(calibration_frame, text="OPEN", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, padx=5)
ctk.CTkLabel(calibration_frame, text="°", font=ctk.CTkFont(weight="bold")).grid(row=0, column=4)


calibration_sliders = {}

for row_index, (name, landmark_id) in enumerate([("Thumb", 3), ("Index", 6), ("Middle", 10), ("Ring", 14), ("Pinky", 18)], start=1):

    ctk.CTkLabel(calibration_frame, text=name).grid(row=row_index, column=0, padx=5, pady=5)

    close_value_label = ctk.CTkLabel(calibration_frame, text=str(closed_values[landmark_id]), width=35)
    close_value_label.grid(row=row_index, column=2, padx=3)

    open_value_label = ctk.CTkLabel(calibration_frame, text=str(open_values[landmark_id]), width=35)
    open_value_label.grid(row=row_index, column=4, padx=3)

    calibration_sliders[landmark_id] = {
        "close_label": close_value_label,
        "open_label": open_value_label
    }


# =========================
# SLIDER CALLBACKS
# =========================

def update_close_value(landmark_id, value):

    value = int(float(value))
    closed_values[landmark_id] = value

    calibration_sliders[landmark_id]["close_label"].configure(text=str(value))


def update_open_value(landmark_id, value):

    value = int(float(value))
    open_values[landmark_id] = value

    calibration_sliders[landmark_id]["open_label"].configure(text=str(value))


for row_index, landmark_id in enumerate([3, 6, 10, 14, 18], start=1):

    close_slider = ctk.CTkSlider(calibration_frame, from_=0, to=180, number_of_steps=180, command=lambda value, landmark_id=landmark_id: update_close_value(landmark_id, value))
    close_slider.set(closed_values[landmark_id])
    close_slider.grid(row=row_index, column=1, padx=5, sticky="ew")

    open_slider = ctk.CTkSlider(calibration_frame, from_=0, to=180, number_of_steps=180, command=lambda value, landmark_id=landmark_id: update_open_value(landmark_id, value))
    open_slider.set(open_values[landmark_id])
    open_slider.grid(row=row_index, column=3, padx=5, sticky="ew")


# =========================
# FOOTER
# =========================

footer = ctk.CTkFrame(root)
footer.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))

telemetry_label = ctk.CTkLabel(footer, text="T:180 I:180 M:180 R:180 P:180", font=ctk.CTkFont(size=14, weight="bold"))
telemetry_label.pack(pady=8)

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

debug_loop_count = 0

fps = 0.0
fps_counter = 0
fps_timer = time.time()

angle_debug_timer = time.time()

process_cpu = 0.0
process_cpu_share = 0.0
process_ram = 0.0
process_ram_percent = 0.0

performance_timer = time.time()

process = psutil.Process()
process_pid = process.pid



logical_cpus = psutil.cpu_count(logical=True)


process.cpu_percent(None)

print("[DEBUG] Entering main camera loop...")
debug_first_frame = True


debug_loop_count += 1

if debug_loop_count == 1:
    print("[DEBUG] Main loop is running")

while cam.isOpened() and running:
    success , frame = cam.read()

    if debug_first_frame:

        if success:
            print("[DEBUG] Camera frame received successfully")
        else:
            print("[DEBUG] ERROR: Camera frame could not be read")

        debug_first_frame = False
    



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


    if debug_first_frame:
        print("[DEBUG] Starting MediaPipe processing...")

    result = detector.detect_for_video(mp_img,timestamp_ms)

    if debug_first_frame:
        print("[DEBUG] MediaPipe processing completed")

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

                    if time.time() - angle_debug_timer >= 1.0:

                        print(
                            f"[ANGLE DEBUG] "
                            f"T:{current_angles_raw[3]:.1f}->{current_angles[3]:.1f}->{smoothed_angles[3]:.1f} "
                            f"I:{current_angles_raw[6]:.1f}->{current_angles[6]:.1f}->{smoothed_angles[6]:.1f} "
                            f"M:{current_angles_raw[10]:.1f}->{current_angles[10]:.1f}->{smoothed_angles[10]:.1f} "
                            f"R:{current_angles_raw[14]:.1f}->{current_angles[14]:.1f}->{smoothed_angles[14]:.1f} "
                            f"P:{current_angles_raw[18]:.1f}->{current_angles[18]:.1f}->{smoothed_angles[18]:.1f}"
                        )

                        print(
                            f"[STATE DEBUG] "
                            f"T:{'CLOSED' if finger_states[3] else 'OPEN'} "
                            f"I:{'CLOSED' if finger_states[6] else 'OPEN'} "
                            f"M:{'CLOSED' if finger_states[10] else 'OPEN'} "
                            f"R:{'CLOSED' if finger_states[14] else 'OPEN'} "
                            f"P:{'CLOSED' if finger_states[18] else 'OPEN'}"
                        )

                        angle_debug_timer = time.time()

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

            print(f"[GESTURE DEBUG] {current_gesture}")


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


    # =========================
    # UPDATE USER INTERFACE
    # =========================

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    image = Image.fromarray(rgb_frame)
    photo = ImageTk.PhotoImage(image=image)

    camera_label.configure(image=photo, text="")
    camera_label.image = photo

    gesture_label.configure(text=f"Gesture: {current_gesture.upper()}")
    fps_label.configure(text=f"FPS: {fps:.1f}")
    cpu_label.configure(text=f"CPU: {process_cpu_share:.1f}% | Raw: {process_cpu:.0f}%")
    ram_label.configure(text=f"RAM: {process_ram:.0f} MB")

    for name, landmark_id in [("Thumb", 3), ("Index", 6), ("Middle", 10), ("Ring", 14), ("Pinky", 18)]:

        finger_labels[landmark_id]["angle"].configure(text=f"{current_angles_raw[landmark_id]:.0f}°")
        finger_labels[landmark_id]["smooth"].configure(text=f"{smoothed_angles[landmark_id]:.0f}°")

        if finger_states[landmark_id]:
            finger_labels[landmark_id]["state"].configure(text="CLOSED")
        else:
            finger_labels[landmark_id]["state"].configure(text="OPEN")
    telemetry_label.configure(text=f"T:{int(smoothed_angles[3])} I:{int(smoothed_angles[6])} M:{int(smoothed_angles[10])} R:{int(smoothed_angles[14])} P:{int(smoothed_angles[18])}")

    root.update()


print("[DEBUG] Shutting down...")

sender_socket.close()
print("[DEBUG] UDP socket closed")

cam.release()
print("[DEBUG] Camera released")

root.destroy()
print("[DEBUG] GUI destroyed")

print("[DEBUG] Program finished")