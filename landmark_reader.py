import cv2
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


base_options = python.BaseOptions(model_asset_path = "hand_landmarker.task")

options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=1,running_mode=vision.RunningMode.VIDEO)

detector = vision.HandLandmarker.create_from_options(options)

cam = cv2.VideoCapture(0)

while cam.isOpened():
    success , frame = cam.read()

    if not success  :
        break

    frame = cv2.flip(frame, 1)

    rgb_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

    mp_img = mp.Image(mp.ImageFormat.SRGB,rgb_frame)

    timestamp_ms = int(time.time() * 1000)

    result = detector.detect_for_video(mp_img,timestamp_ms)

    if result.hand_landmarks:
        for hand_landmarks in result.hand_landmarks :
            for landmark_id , landmark in enumerate(hand_landmarks):
                x = landmark.x
                y = landmark.y
                z = landmark.z

                print(x,y,z)

    else :
        print("No Hand Detected")

    cv2.imshow("Varad", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break







cam.release()
cv2.destroyAllWindows()