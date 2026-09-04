import cv2
import time
import numpy as np 
import math 
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

frame_h = 600

frame_w = 680

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

cam = cv2.VideoCapture(0)

finger_states = {3: False, 6: False, 10: False, 14: False, 18: False}
pinch_states = {8: False, 12: False, 16: False, 20: False}

current_gesture = "NO HAND"
current_angles_raw = {3: 0.0, 6: 0.0, 10: 0.0, 14: 0.0, 18: 0.0}
current_angles = {3: 0.0, 6: 0.0, 10: 0.0, 14: 0.0, 18: 0.0}

while cam.isOpened():
    success , frame = cam.read()

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

                    finger_states[landmark_id] = latency_checker(result_angle, closed_values[landmark_id], open_values[landmark_id], finger_states[landmark_id])

                    # print(f"ID: {finger_id}  Bent: {verdict} Angle: {result_angle} ")
                    
                    # print(f"ID: {landmark_id}  Angle: {result_angle}")

                    # print(landmark_id)
                    # print(pixel_x , pixel_y )

                
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

            gesture = gesture_finder(signals)
            current_gesture = gesture

            print(f"Thumb:{signals['thumb_bend']} Index:{signals['index_bend']} Middle:{signals['middle_bend']} Ring:{signals['ring_bend']} Pinky:{signals['pinky_bend']} | Idx-Pinch:{signals['index_pinch']} Mid-Pinch:{signals['middle_pinch']} Ring-Pinch:{signals['ring_pinch']} Pnk-Pinch:{signals['pinky_pinch']} Gesture:{gesture}")

                    # print(landmark_id)
                    # print(pixel_x , pixel_y )
                    

                # x = landmark.x
                # y = landmark.y
                # z = landmark.z

                # print(landmark_id)
                # print(landmark)

                # print(hand_landmarks)

                # pixel_x = int(x*w)
                # pixel_y = int(y*h)

                # print(landmark_id)
                # print(pixel_x , pixel_y )


            mp_drawing.draw_landmarks(frame, hand_landmarks,mp_hands.HAND_CONNECTIONS,mp_drawing_styles.get_default_hand_landmarks_style(),mp_drawing_styles.get_default_hand_connections_style())

            # mp_drawing.draw_landmarks(frame, hand_landmarks,mp_hands.HAND_CONNECTIONS, landmark_look, connections_look )

    else :
        print("No Hand Detected")
        current_gesture = "NO HAND"
        current_angles_raw = {3: 180.0, 6: 180.0, 10: 180.0, 14: 180.0, 18: 180.0}
        current_angles = {3: 180.0, 6: 180.0, 10: 180.0, 14: 180.0, 18: 180.0}
    
    print(current_angles)
      
    TOP_BAR_H = 100
    BOTTOM_BAR_H = 50
    CANVAS_W = frame_w
    CANVAS_H = frame_h + TOP_BAR_H + BOTTOM_BAR_H

    canvas = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.uint8)
    canvas[:] = (35, 35, 35)


    canvas[TOP_BAR_H : TOP_BAR_H + frame_h, 0 : CANVAS_W] = frame


                
    cv2.putText(canvas, f"Gesture: {current_gesture.upper()}", (15, 75), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)


    telemetry_raw = f"T:{int(current_angles_raw[3])} I:{int(current_angles_raw[6])} M:{int(current_angles_raw[10])} R:{int(current_angles_raw[14])} P:{int(current_angles_raw[18])}"
    telemetry = f"T:{int(current_angles[3])} I:{int(current_angles[6])} M:{int(current_angles[10])} R:{int(current_angles[14])} P:{int(current_angles[18])}"

    cv2.putText(canvas, telemetry, (15, CANVAS_H - 15), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 191, 0), 2, cv2.LINE_AA)



    cv2.imshow("Hand Landmark & Finger Angle Tracker", canvas)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break





cam.release()
cv2.destroyAllWindows()