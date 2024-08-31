import threading
import time
import serial
import adafruit_fingerprint
import nfc
import tkinter as tk
from tkinter import ttk, font, messagebox
from datetime import datetime
import RPi.GPIO as GPIO
import requests

# Global flag to control NFC activation
nfc_enabled = threading.Event()

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

# Initialize the fingerprint sensor
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
                # Record Time-In and unlock door
                record_time_in(finger.finger_id, name)
                unlock_door()
                messagebox.showinfo("Welcome", f"Welcome, {name}! Door unlocked.")
                nfc_enabled.set()  # Enable NFC reader after a successful fingerprint match
                root.after(5000, lock_door)  # Lock the door after 5 seconds
            else:
                # Record Time-Out and lock door
                record_time_out(finger.finger_id)
                lock_door()
                messagebox.showinfo("Goodbye", f"Goodbye, {name}! Door locked.")
                root.after(5000, auto_scan_fingerprint)  # Wait 5 seconds then resume scanning
        else:
            root.after(5000, auto_scan_fingerprint)  # Wait 5 seconds then resume scanning
    else:
        messagebox.showinfo("No Match", "No matching fingerprint found in the database.")

#Initialize the NFC reader
def nfc_task(nfc_status, uid_display):
    def on_connect(tag):
        # Extract and display the UID of the NFC tag
        uid = tag.identifier.hex().upper()
        nfc_status.set(f"NFC Tag detected! UID: {uid}")
        uid_display.set(uid)  # Update the UID display in the Tkinter GUI

        # Simulate adding data to the table (example data)
        add_table_entry("2024-08-31", "John Doe", "PC1", "123456", "4th Year", "CS4A", "Prof. Smith", "08:00 AM", "12:00 PM")

    try:
        clf = nfc.ContactlessFrontend('usb')

        while True:
            # Wait until NFC is enabled by the fingerprint match
            nfc_enabled.wait()
            nfc_status.set("NFC reader active. Waiting for NFC tag...")

            clf.connect(rdwr={'on-connect': on_connect})

            # Reset the event so the NFC task waits for the next fingerprint match
            nfc_enabled.clear()
            nfc_status.set("NFC reader waiting for fingerprint match...")

            time.sleep(1)

    except Exception as e:
        nfc_status.set(f"Error: {e}")

# Function to add an entry to the table
def add_table_entry(date, name, pc, student_number, year, section, faculty, time_in, time_out):
    table.insert("", "end", values=(date, name, pc, student_number, year, section, faculty, time_in, time_out))

# Update the real-time date and time display
def update_time():
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    time_label.config(text=f"Current Date and Time: {current_time}")
    root.after(1000, update_time)  # Update every second

# Create the main Tkinter window
root = tk.Tk()
root.title("Fingerprint and NFC Reader")

# Set up the layout
root.geometry("700x500")

# Create a frame for the real-time date and time display
time_frame = ttk.Frame(root, padding="10")
time_frame.pack(side="top", fill="x")

time_label = ttk.Label(time_frame, text="", font=("Arial", 14))
time_label.pack()

# Create a top frame to hold the fingerprint and NFC frames side by side
top_frame = ttk.Frame(root, padding="10")
top_frame.pack(side="top", fill="x")

# Create a frame for the fingerprint sensor on the left
left_frame = ttk.Frame(top_frame, padding="10")
left_frame.pack(side="left", fill="y", expand=True)

fingerprint_label = ttk.Label(left_frame, text="Fingerprint Sensor", font=("Arial", 16))
fingerprint_label.pack(pady=20)

# Create a frame for the NFC reader on the right
right_frame = ttk.Frame(top_frame, padding="10")
right_frame.pack(side="right", fill="y", expand=True)

nfc_label = ttk.Label(right_frame, text="NFC Reader", font=("Arial", 16))
nfc_label.pack(pady=20)

nfc_status = tk.StringVar()
nfc_status_label = ttk.Label(right_frame, textvariable=nfc_status, wraplength=250)
nfc_status_label.pack()

# Label to display the detected UID
uid_label = ttk.Label(right_frame, text="UID:", font=("Arial", 14))
uid_label.pack(pady=10)

uid_display = tk.StringVar()
uid_display_label = ttk.Label(right_frame, textvariable=uid_display, font=("Arial", 14))
uid_display_label.pack()

# Create a frame for the table below the top frame
table_frame = ttk.Frame(root, padding="10")
table_frame.pack(side="bottom", fill="both", expand=True)

# Create the table with the specified columns
columns = ("Date", "Name", "PC", "Student Number", "Year", "Section", "Faculty", "Time-in", "Time-out")
table = ttk.Treeview(table_frame, columns=columns, show="headings")

# Set proportional column widths
column_widths = [80, 120, 40, 100, 70, 70, 120, 80, 80]

for col, width in zip(columns, column_widths):
    table.heading(col, text=col)
    table.column(col, anchor="center", width=width)

table.pack(fill="both", expand=True)

# Start the fingerprint and NFC tasks in separate threads
fingerprint_thread = threading.Thread(target=fingerprint_task, args=(fingerprint_status,))
nfc_thread = threading.Thread(target=nfc_task, args=(nfc_status, uid_display))

fingerprint_thread.start()
nfc_thread.start()

# Start the real-time clock update
update_time()

# Start the Tkinter main loop
root.mainloop()

Traceback (most recent call last):
  File "/home/miko/Downloads/prolockv2/prolockv3/main.py", line 283
    fingerprint_thread = threading.Thread(target=auto_scan_fingerprint))
                                                                       ^
SyntaxError: unmatched ')'

# Ensure threads are cleaned up properly
fingerprint_thread.join()
nfc_thread.join()
