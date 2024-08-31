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
TIME_IN_FINGERPRINT_URL = "https://prolocklogger.pro/api/logs/time-in/fingerprint"
TIME_OUT_FINGERPRINT_URL = "https://prolocklogger.pro/api/logs/time-out/fingerprint"
RECENT_LOGS_FINGERPRINT_URL2 = 'https://prolocklogger.pro/api/recent-logs/by-fingerid'

USER_INFO_URL = 'https://prolocklogger.pro/api/user-information/by-id-card'
RECENT_LOGS_URL = 'https://prolocklogger.pro/api/recent-logs'
TIME_IN_URL = 'https://prolocklogger.pro/api/logs/time-in'
TIME_OUT_URL = 'https://prolocklogger.pro/api/logs/time-out'
RECENT_LOGS_URL2 = 'https://prolocklogger.pro/api/recent-logs/by-uid'

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

# Global variables
root = tk.Tk()
running = True
script_run = False
time_in_records = set()
time_out_records = set()

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

def check_time_in_record_fingerprint(fingerprint_id):
    """Check if there is a Time-In record for the given fingerprint ID."""
    try:
        url = f"{RECENT_LOGS_FINGERPRINT_URL2}?fingerprint_id={fingerprint_id}"
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

def record_time_in_fingerprint(fingerprint_id, user_name, role_id="2"):
    try:
        url = f"{TIME_IN_FINGERPRINT_URL}?fingerprint_id={fingerprint_id}&time_in={datetime.now().strftime('%H:%M')}&user_name={user_name}&role_id={role_id}"
        response = requests.put(url)
        response.raise_for_status()
        result = response.json()
        print(result)
        messagebox.showinfo("Success", "Time-In recorded successfully.")
    except requests.RequestException as e:
        messagebox.showerror("Error", f"Error recording Time-In: {e}")

def record_time_out_fingerprint(fingerprint_id):
    """Record the Time-Out event for the given fingerprint ID."""
    try:
        # Prepare URL with query parameters
        url = f"{TIME_OUT_FINGERPRINT_URL}?fingerprint_id={fingerprint_id}&time_out={datetime.now().strftime('%H:%M')}"
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
            if not check_time_in_record_fingerprint(finger.finger_id):
                # Record Time-In and unlock door
                record_time_in_fingerprint(finger.finger_id, name)
                unlock_door()
                messagebox.showinfo("Welcome", f"Welcome, {name}! Door unlocked.")
                nfc_enabled.set()  # Enable NFC reader after a successful fingerprint match
                root.after(5000, lock_door)  # Lock the door after 5 seconds
            else:
                # Record Time-Out and lock door
                record_time_out_fingerprint(finger.finger_id)
                lock_door()
                messagebox.showinfo("Goodbye", f"Goodbye, {name}! Door locked.")
                root.after(5000, auto_scan_fingerprint)  # Wait 5 seconds then resume scanning
        else:
            root.after(5000, auto_scan_fingerprint)  # Wait 5 seconds then resume scanning
    else:
        messagebox.showinfo("No Match", "No matching fingerprint found in the database.")

# Start of NFC READER Functions
def fetch_user_info(uid):
    try:
        url = f'{USER_INFO_URL}?id_card_id={uid}'
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()

        user_number = data.get('user_number') or 'None'
        user_name = data.get('user_name') or 'None'
        year = data.get('year') or 'None'
        block = data.get('block') or 'None'

        student_number_entry.delete(0, tk.END)
        student_number_entry.insert(0, user_number)

        name_entry.delete(0, tk.END)
        name_entry.insert(0, user_name)

        year_entry.delete(0, tk.END)
        year_entry.insert(0, year)

        section_entry.delete(0, tk.END)
        section_entry.insert(0, block)

        error_label.config(text="")  # Clear any previous error message

        if check_time_in_record(uid):
            record_time_out(uid)
        else:
            record_time_in(uid, user_name, year)

        update_records(uid)

    except requests.HTTPError as http_err:
        if response.status_code == 404:
            clear_data()
            update_result("Card is not registered, Please contact the administrator.")
        else:
            update_result(f"HTTP error occurred: {http_err}")
    except requests.RequestException as e:
        update_result(f"Error fetching user info: {e}")

def update_records(uid):
    if check_time_in_record(uid):
        time_in_records.add(uid)
    else:
        time_out_records.add(uid)

def check_time_in_record(rfid_number):
    try:
        url = f'{RECENT_LOGS_URL2}?rfid_number={rfid_number}'
        response = requests.get(url)
        response.raise_for_status()

        logs = response.json()
        for log in logs:
            if log.get('time_in') and not log.get('time_out'):
                return True

        return False

    except requests.RequestException as e:
        update_result(f"Error checking Time-In record: {e}")
        return False

def record_time_in(rfid_number, user_name, year):
    try:
        url = f"{TIME_IN_URL}?rfid_number={rfid_number}&time_in={datetime.now().strftime('%H:%M')}&year={year}&user_name={user_name}&role_id=3"
        response = requests.put(url)
        response.raise_for_status()
        result = response.json()
        print(result)
        update_result("Time-In recorded successfully.")
        fetch_recent_logs()

    except requests.RequestException as e:
        update_result(f"Error recording Time-In: {e}")

def record_time_out(rfid_number):
    try:
        if not check_time_in_record(rfid_number):
            update_result("No Time-In record found for this RFID. Cannot record Time-Out.")
            return

        url = f"{TIME_OUT_URL}?rfid_number={rfid_number}&time_out={datetime.now().strftime('%H:%M')}"
        response = requests.put(url)
        response.raise_for_status()
        result = response.json()
        print(result)
        update_result("Time-Out recorded successfully.")
        fetch_recent_logs()

    except requests.RequestException as e:
        update_result(f"Error recording Time-Out: {e}")

def fetch_recent_logs():
    try:
        response = requests.get(RECENT_LOGS_URL)
        response.raise_for_status()

        logs = response.json()

        # Clear existing logs
        for i in table.get_children():  # Corrected from logs_tree to table
            table.delete(i)

        # Insert new logs
        for log in logs:
            table.insert("", "end", values=(
                log['user_name'],
                log['block_name'],
                log['year'],
                log['time_in'],
                log['time_out']
            ))

    except requests.RequestException as e:
        update_result(f"Error fetching recent logs: {e}")

def clear_data():
    student_number_entry.delete(0, tk.END)
    name_entry.delete(0, tk.END)
    year_entry.delete(0, tk.END)
    section_entry.delete(0, tk.END)

def update_result(message):
    error_label.config(text=message)

def on_closing():
    global running
    running = False
    if thread.is_alive():
        thread.join()
    if hasattr(clf, 'close') and clf is not None:
        clf.close()
    root.destroy()

# Initialize the NFC reader
def nfc_task(nfc_status, uid_display):
    global running
    while running:
        try:
            tag = clf.connect(rdwr={'on-connect': lambda tag: False})
            if tag:
                uid = tag.identifier.hex()
                fetch_user_info(uid)
                time.sleep(1)

            if script_run:
                running = False
                root.quit()  # Terminate the Tkinter main loop

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

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

# Define custom fonts
label_font = font.Font(family="Helvetica", size=12)

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

# Student Information Frame
info_frame = tk.Frame(root)
info_frame.pack(pady=10)

# Date
date_label = tk.Label(info_frame, text="Date:", font=label_font)
date_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')
date_entry = tk.Entry(info_frame, font=label_font)
date_entry.grid(row=0, column=1, padx=10, pady=5)

# Name
name_label = tk.Label(info_frame, text="Name:", font=label_font)
name_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')
name_entry = tk.Entry(info_frame, font=label_font)
name_entry.grid(row=1, column=1, padx=10, pady=5)

# PC
pc_label = tk.Label(info_frame, text="PC:", font=label_font)
pc_label.grid(row=2, column=0, padx=10, pady=5, sticky='w')
pc_entry = tk.Entry(info_frame, font=label_font)
pc_entry.grid(row=2, column=1, padx=10, pady=5)

# Student Number
student_number_label = tk.Label(info_frame, text="Student Number:", font=label_font)
student_number_label.grid(row=3, column=0, padx=10, pady=5, sticky='w')
student_number_entry = tk.Entry(info_frame, font=label_font)
student_number_entry.grid(row=3, column=1, padx=10, pady=5)

# Year
year_number_label = tk.Label(info_frame, text="Year:", font=label_font)
year_number_label.grid(row=4, column=0, padx=10, pady=5, sticky='w')
year_number_entry = tk.Entry(info_frame, font=label_font)
year_number_entry.grid(row=4, column=1, padx=10, pady=5)

# Section
section_number_label = tk.Label(info_frame, text="Section:", font=label_font)
section_number_label.grid(row=5, column=0, padx=10, pady=5, sticky='w')
section_number_entry = tk.Entry(info_frame, font=label_font)
section_number_entry.grid(row=5, column=1, padx=10, pady=5)

# Faculty
faculty_number_label = tk.Label(info_frame, text="Faculty:", font=label_font)
faculty_number_label.grid(row=6, column=0, padx=10, pady=5, sticky='w')
faculty_number_entry = tk.Entry(info_frame, font=label_font)
faculty_number_entry.grid(row=6, column=1, padx=10, pady=5)

error_label = tk.Label(root, text="", font=("Helvetica", 10, "bold", "italic"), foreground="red")
error_label.pack(pady=10)

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
fingerprint_thread = threading.Thread(target=auto_scan_fingerprint)
nfc_thread = threading.Thread(target=nfc_task, args=(nfc_status, uid_display))

# Fetch and display recent logs
fetch_recent_logs()

fingerprint_thread.start()
nfc_thread.start()

# Start the real-time clock update
update_time()

# Start the Tkinter main loop
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()

# Ensure threads are cleaned up properly
fingerprint_thread.join()
nfc_thread.join()
