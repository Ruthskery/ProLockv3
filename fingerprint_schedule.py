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
import atexit

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
# Do not set an initial state; it will be adjusted based on solenoid status

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
    GPIO.output(SOLENOID_PIN, GPIO.LOW)
    print("Door unlocked.")

def lock_door():
    GPIO.output(SOLENOID_PIN, GPIO.HIGH)
    print("Door locked.")

def run_rfid_script():
    # Close the current frame and run the RFID script
    root.destroy()  # Close current frame
    subprocess.Popen(["python3", "debug_nfc.py"])  # Run RFID script

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
            if log.get('time_in') and not log.get('time_out'):
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

def get_schedule(fingerprint_id):
    try:
        response = requests.get(f"https://prolocklogger.pro/api/lab-schedules/fingerprint/{fingerprint_id}")
        if response.status_code == 200:
            schedules = response.json()
            if schedules:
                today = datetime.now().strftime('%A')  # Get the current day of the week
                current_time = datetime.now().strftime('%H:%M')  # Get the current time
                for schedule in schedules:
                    if schedule['day_of_the_week'] == today:
                        start_time = schedule['class_start']
                        end_time = schedule['class_end']
                        if start_time <= current_time <= end_time:
                            return True  # Schedule matches, allow access
            return False  # No matching schedule or not within allowed time
        else:
            messagebox.showerror("API Error", "Failed to fetch schedule from API.")
            return False
    except requests.RequestException as e:
        messagebox.showerror("Request Error", f"Failed to connect to API: {e}")
        return False


def auto_scan_fingerprint():
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
        if get_schedule(finger.finger_id):  # Check if the current time is within the allowed schedule
            if not check_time_in_record(finger.finger_id):
                # Record Time-In, unlock door, and transition to RFID scanning
                record_time_in(finger.finger_id, name)
                unlock_door()
                messagebox.showinfo("Welcome", f"Welcome, {name}! Door unlocked.")
                root.after(1000, run_rfid_script)  # Wait 1 second then run RFID script
            else:
                # Record Time-Out and lock door
                record_time_out(finger.finger_id)
                lock_door()
                messagebox.showinfo("Goodbye", f"Goodbye, {name}! Door locked.")
                root.after(5000, auto_scan_fingerprint)  # Wait 10 seconds then resume scanning
        else:
            messagebox.showinfo("Access Denied", "Access is not allowed outside of scheduled times.")
            root.after(5000, auto_scan_fingerprint)  # Wait 10 seconds then resume scanning
    else:
        messagebox.showinfo("No Match", "No matching fingerprint found in the database.")

def lock_door_and_resume():
    auto_scan_fingerprint()  # Resume fingerprint scanning without locking the door
def center_widget(parent, widget, width, height, y_offset=0):
    """Center a widget within its parent, optionally with a vertical offset."""
    parent_width = parent.winfo_width()
    x = (parent_width - width) // 2
    y = y_offset
    widget.place(x=x, y=y)
    return y + height

# Initialize the main window
root = tk.Tk()
root.configure(bg='#f0f0f0')
root.title("Fingerprint Scanning")

# Fit the root window to the screen resolution
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
root.geometry(f"{screen_width}x{screen_height}")

# Set panel dimensions
panel_width = 600
panel_height = 400

# Create the panel (center it within the root window)
panel = tk.Frame(root, bg='#B4CBEF')
panel.place(x=(screen_width - panel_width) // 2, y=(screen_height - panel_height) // 2, width=panel_width, height=panel_height)
# Define custom fonts for headings
heading_font = font.Font(family="Helvetica", size=20, weight="bold")
subheading_font = font.Font(family="Helvetica", size=14, weight="normal")

# Create widgets
main_heading = tk.Label(panel, text="Fingerprint Scanning", font=heading_font, bg='#B4CBEF')
subheading = tk.Label(panel, text="Faculty Fingerprint", font=subheading_font, bg='#B4CBEF')

# Load and resize an image
image_path = "fingericon.png"  # Replace with your image file path
desired_width = 200
desired_height = 180

image = Image.open(image_path)
image = image.resize((desired_width, desired_height))
photo = ImageTk.PhotoImage(image)
image_label = tk.Label(panel, image=photo, bg='#B4CBEF')

# Update the dimensions of widgets after creating them
root.update_idletasks()

# Define vertical spacing between widgets
vertical_spacing = 20  # Space between widgets

# Place widgets sequentially from top to bottom
current_y = vertical_spacing

current_y = center_widget(panel, main_heading, main_heading.winfo_reqwidth(), main_heading.winfo_reqheight(), current_y)
current_y += vertical_spacing  # Add spacing below the heading

current_y = center_widget(panel, subheading, subheading.winfo_reqwidth(), subheading.winfo_reqheight(), current_y)
current_y += vertical_spacing  # Add spacing below the subheading

center_widget(panel, image_label, desired_width, desired_height, current_y)

# Start scanning for fingerprint
root.after(1000, auto_scan_fingerprint)  # Start the fingerprint scan after 1 second

# Define a cleanup function to ensure GPIO is handled correctly
def cleanup():
    # Optionally, you can choose to keep the GPIO state as is
    print("Cleanup called.")

# Register the cleanup function to be called on exit
atexit.register(cleanup)

# Run the Tkinter event loop
root.mainloop()

