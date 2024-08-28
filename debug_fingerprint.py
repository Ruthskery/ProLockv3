import tkinter as tk
from tkinter import font, messagebox
from PIL import Image, ImageTk
import serial
import adafruit_fingerprint
import RPi.GPIO as GPIO
import time
import subprocess
import requests
from datetime import datetime

# API URLs
api_url = "https://prolocklogger.pro/api/getuserbyfingerprint/"
TIME_IN_URL = "https://prolocklogger.pro/api/logs/time-in/fingerprint"
TIME_OUT_URL = "https://prolocklogger.pro/api/logs/time-out/fingerprint"
RECENT_LOGS_URL2 = 'https://prolocklogger.pro/api/recent-logs/by-fingerid'

# GPIO pin configuration for the solenoid lock
SOLENOID_PIN = 17

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(SOLENOID_PIN, GPIO.OUT)
GPIO.output(SOLENOID_PIN, GPIO.LOW)  # Ensure lock is in default state (locked)

# Initialize serial connection
def initialize_serial():
    try:
        uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)
        return adafruit_fingerprint.Adafruit_Fingerprint(uart)
    except serial.SerialException as e:
        messagebox.showerror("Serial Error", f"Failed to connect to serial port: {e}")
        return None

finger = initialize_serial()

# State variables
unlock_attempt = True
external_script_process = None

def unlock_door():
    GPIO.output(SOLENOID_PIN, GPIO.HIGH)
    print("Door unlocked.")

def lock_door():
    GPIO.output(SOLENOID_PIN, GPIO.LOW)
    print("Door locked.")

def run_external_script():
    global external_script_process
    try:
        external_script_process = subprocess.Popen(["python3", "debug_nfc.py"])
        print("External script executed.")
    except Exception as e:
        messagebox.showerror("Execution Error", f"Failed to run external script: {e}")

def terminate_external_script():
    global external_script_process
    if external_script_process:
        external_script_process.terminate()
        print("External script terminated.")
def get_user_details(fingerprint_id):
    try:
        response = requests.get(f"{api_url}{fingerprint_id}")
        if response.status_code == 200:
            data = response.json()
            if 'name' in data:
                return data['name']
        messagebox.showerror("API Error", "Failed to fetch data from API.")
        return None
    except requests.RequestException as e:
        messagebox.showerror("Request Error", f"Failed to connect to API: {e}")
        return None

def check_time_in_record(fingerprint_id):
    """Check if there is a Time-In record for the given fingerprint ID."""
    try:
        url = f"{RECENT_LOGS_URL2}?fingerprint_id={fingerprint_id}"
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes

        # Assuming the response is a list of logs
        logs = response.json()
        for log in logs:
            if isinstance(log, dict) and log.get('time_in') and not log.get('time_out'):
                return True  # Time-In record exists and Time-Out has not been recorded

        return False

    except requests.RequestException as e:
        print(f"Error checking Time-In record: {e}")
        return False

def record_time_in(fingerprint_id, user_name, role_id="2"):
    try:
        url = f"{TIME_IN_URL}?fingerprint_id={fingerprint_id}&time_in={datetime.now().strftime('%H:%M')}&user_name={user_name}&role_id={role_id}"
        response = requests.put(url)
        response.raise_for_status()
        result = response.json()
        print(result)
        messagebox.showinfo("Success", "Time-In recorded successfully.")
    except requests.RequestException as e:
        messagebox.showerror("Error", f"Error recording Time-In: {e}")

def record_time_out(fingerprint_id):
    """Record the Time-Out event for the given fingerprint ID."""
    try:
        # Check if a Time-In record exists for this fingerprint ID
        if not check_time_in_record(fingerprint_id):
            print("No Time-In record found for this fingerprint ID. Cannot record Time-Out.")
            return

        # Prepare URL with query parameters
        url = f"{TIME_OUT_URL}?fingerprint_id={fingerprint_id}&time_out={datetime.now().strftime('%H:%M')}"
        response = requests.put(url)
        response.raise_for_status()  # Raise an error for bad status codes

        # Parse the JSON response
        result = response.json()
        print(result)
        print("Time-Out recorded successfully.")

    except requests.RequestException as e:
        print(f"Error recording Time-Out: {e}")
def auto_scan_fingerprint():
    """Automatically scan the fingerprint and handle user actions."""
    global unlock_attempt

    if not finger:
        return

    print("Waiting for image...")
    while finger.get_image() != adafruit_fingerprint.OK:
        pass

    print("Templating...")
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        messagebox.showwarning("Error", "Failed to template the fingerprint image.")
        root.after(5000, auto_scan_fingerprint)  # Retry after 5 seconds
        return
    print("Searching...")
    if finger.finger_search() != adafruit_fingerprint.OK:
        messagebox.showwarning("Error", "Failed to search for fingerprint match.")
        root.after(5000, auto_scan_fingerprint)  # Retry after 5 seconds
        return

    print("Detected #", finger.finger_id, "with confidence", finger.confidence)
    
    # Fetch user details using API
    name = get_user_details(finger.finger_id)

    if name:
        # Check if there is a Time-In record
        if check_time_in_record(finger.finger_id):
            # If Time-In record exists, record Time-Out
            if unlock_attempt:
                unlock_door()
                messagebox.showinfo("Welcome", f"Welcome, {name}! Door unlocked.")
                
                # Run external script and wait for 10 seconds
                run_external_script()
                # root.after(30000, terminate_external_script)  # Wait 30 seconds then terminate the external script
                # root.after(30000, lock_door_and_resume)  # Wait 30 seconds then lock the door and resume
                unlock_attempt = False  # Next scan will lock the door
            else:
                record_time_out(finger.finger_id)  # Record Time-Out
                lock_door()
                messagebox.showinfo("Goodbye", f"Goodbye, {name}! Door locked.")
                #run_external_script()
                # root.after(10000, terminate_external_script)  # Wait 10 seconds then terminate the external script
                # root.after(10000, lock_door_and_resume)  # Wait 10 seconds then lock the door and resume
                unlock_attempt = True  # Ready for the next unlock attempt
        else:
            # If no Time-In record, record Time-In
            record_time_in(finger.finger_id, name)
            unlock_door()
            messagebox.showinfo("Welcome", f"Welcome, {name}! Door unlocked.")
            
            # Run external script and wait for 10 seconds
            run_external_script()
            root.after(30000, terminate_external_script)  # Wait 30 seconds then terminate the external script
            root.after(30000, lock_door_and_resume)  # Wait 30 seconds then lock the door and resume
            unlock_attempt = False  # Next scan will lock the door
    else:
        messagebox.showinfo("No Match", "No matching fingerprint found in the database.")

def lock_door_and_resume():
    lock_door()
    auto_scan_fingerprint()  # Resume fingerprint scanning after locking the door

def center_window(window, width, height):
    """Center the window on the screen."""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    # Calculate the x and y coordinates for the window to be centered
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)

    # Set the window geometry
    window.geometry(f'{width}x{height}+{x}+{y}')

# Initialize the main window
root = tk.Tk()
root.configure(bg='#f0f0f0')
root.title("Fingerprint Scanning")

# Define custom fonts for headings
heading_font = font.Font(family="Helvetica", size=20, weight="bold")
subheading_font = font.Font(family="Helvetica", size=14, weight="normal")

# Create the main heading
main_heading = tk.Label(root, text="Fingerprint Scanning", font=heading_font, bg='#f0f0f0')
main_heading.place(x=110, y=30)

# Create the subheading
subheading = tk.Label(root, text="Faculty Fingerprint", font=subheading_font, bg='#f0f0f0')
subheading.place(x=170, y=80)

# Load and resize an image
image_path = "fingericon.png"  # Replace with your image file path
desired_width = 200  # Set your desired width
desired_height = 180  # Set your desired height

# Open the image file
image = Image.open(image_path)

# Resize the image
image = image.resize((desired_width, desired_height))
photo = ImageTk.PhotoImage(image)
image_label = tk.Label(root, image=photo, bg='#f0f0f0')
image_label.place(x=150, y=140)

# Center the window
center_window(root, 500, 400)

# Start scanning for fingerprint
root.after(1000, auto_scan_fingerprint)  # Start the fingerprint scan after 1 second

# Run the Tkinter event loop
root.mainloop()

# Clean up GPIO settings on exit
GPIO.cleanup()

