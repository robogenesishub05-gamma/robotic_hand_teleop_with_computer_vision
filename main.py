import socket
import network
import time
import machine
from machine import PWM, Pin




WIFI_NAME = "Airtel_PATIL_7427"
WIFI_PASSWORD = "Swami@22010811"
PORT = 5005



wlan = network.WLAN(network.STA_IF)
wlan.active(True)
time.sleep(0.5)


led = Pin(2, Pin.OUT)


def connect_to_wifi():
    wlan.disconnect()
    print("Attempting to connect to WIFI...")
    wlan.connect(WIFI_NAME,WIFI_PASSWORD)
    timeout = 20  		
    while not wlan.isconnected() and timeout > 0:
        time.sleep(0.5)
        timeout -= 1
    if wlan.isconnected():
        return True
    else:
        return False
    
def duty_cycle_value(angle):
    angle = max(0, min(180, angle))
    pulse_ms = 0.5 + (angle / 180.0) * 2.0
    return int((pulse_ms / 20.0) * 65535)

def parse_angles(msg):
    msg = msg.decode('utf-8').strip()
    angle_strings = msg.split(',')
    if len(angle_strings) == 5 :
        angles_list = [float(x) for x in angle_strings]
        return angles_list
    else:
        return None

    
    
servos = [PWM(Pin(13), freq=50),PWM(Pin(12), freq=50),PWM(Pin(14), freq=50),PWM(Pin(27), freq=50),PWM(Pin(26), freq=50)]

def set_to_open():
    for i in range(5):
        duty_value = duty_cycle_value(180)
        servos[i].duty_u16(duty_value)
    print("Moved all the servos to the starting position")
    
set_to_open()
    
if connect_to_wifi():
    ip_address = wlan.ifconfig()[0]
    print("The ESP has successfully established connection with the WIFI")
    print("The IP Address is :",ip_address)
    for _ in range(1):
        led.value(1)  
        time.sleep(1)  
        led.value(0)  
        time.sleep(1)  
else: 
    print("The ESP FAILED to establish a connection with the WIFI")
    for _ in range(2):
        led.value(1)  
        time.sleep(0.5)  
        led.value(0)  
        time.sleep(1)

    
    
if wlan.isconnected():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', PORT))
    sock.settimeout(2)
    print("Listening for UDP packets...")
    while True:
        try :
            msg, address = sock.recvfrom(1024)
            
            
            angles_list = parse_angles(msg)
            if angles_list:
                for i in range(5):
                    angle = float(angles_list[i])
                    duty_value = duty_cycle_value(angle)
                    servos[i].duty_u16(duty_value)
                print("Moved servos to:", angles_list)
            else:
                print("Error: malformed packet:", msg)
                    
        except OSError :
            print(" The system experienced an OSError ")
            set_to_open() 
            for _ in range(3):
                led.value(1)  
                time.sleep(0.5)  
                led.value(0)  
                time.sleep(0.5)
            
        
        
    
        
            
            
    

    