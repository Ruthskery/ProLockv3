import threading
import time
import serial
import adafruit_fingerprint
import nfc
import tkinter as tk
from tkinter import ttk, font, messagebox
import RPi.GPIO as GPIO
import requests

# Global flags and settings
nfc_enabled = threading.Event()
unlock_attempt = True

# API URLs for Fingerprint, NFC, and Current Date-Time
FINGERPRINT_API_URL = "https://prolocklogger.pro/api/getuserbyfingerprint/"
TIME_IN_FINGERPRINT_URL = "https://prolocklogger.pro/api/logs/time-in/fingerprint"
TIME_OUT_FINGERPRINT_URL = "https://prolocklogger.pro/api/logs/time-out/fingerprint"
RECENT_LOGS_FINGERPRINT_URL2 = 'https://prolocklogger.pro/api/recent-logs/by-fingerid'

USER_INFO_URL = 'https://prolocklogger.pro/api/user-information/by-id-card'
RECENT_LOGS_URL = 'https://prolocklogger.pro/api/recent-logs'
TIME_IN_URL = 'https://prolocklogger.pro/api/logs/time-in'
TIME_OUT_URL = 'https://prolocklogger.pro/api/logs/time-out'
RECENT_LOGS_URL2 = 'https://prolocklogger.pro/api/recent-logs/by-uid'
CURRENT_DATE_TIME_URL = 'https://prolocklogger.pro/api/current-date-time'
LAB_SCHEDULE_URL = 'https://prolocklogger.pro/api/lab-schedules/fingerprint/'  # Added for schedule check

# GPIO pin configuration for the solenoid lock
SOLENOID_PIN = 17

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(SOLENOID_PIN, GPIO.OUT)


# Initialize serial connection for fingerprint sensor
def initialize_serial():
    try:
        uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)
        return adafruit_fingerprint.Adafruit_Fingerprint(uart)
    except serial.SerialException as e:
        messagebox.showerror("Serial Error", f"Failed to connect to serial port: {e}")
        return None


finger = initialize_serial()


def unlock_door():
    GPIO.output(SOLENOID_PIN, GPIO.LOW)
    print("Door unlocked.")


def lock_door():
    GPIO.output(SOLENOID_PIN, GPIO.HIGH)
    print("Door locked.")


def get_user_details(fingerprint_id):
    try:
        response = requests.get(f"{FINGERPRINT_API_URL}{fingerprint_id}")
        if response.status_code == 200:
            data = response.json()
            return data.get('name', None)
        messagebox.showerror("API Error", "Failed to fetch data from API.")
        return None
    except requests.RequestException as e:
        messagebox.showerror("Request Error", f"Failed to connect to API: {e}")
        return None


def fetch_current_date_time():
    """Fetches the current date and time from the API."""
    try:
        response = requests.get(CURRENT_DATE_TIME_URL)
        response.raise_for_status()
        data = response.json()  # Expected response: {'day_of_week': 'Sunday', 'date': '01', 'year': '2024', 'month': 'September', 'current_time': '17:04'}

        # Validate the API response contains the necessary fields
        if 'day_of_week' in data and 'current_time' in data:
            return data
        else:
            print("Error: Missing expected keys in the API response.")
            return None
    except requests.RequestException as e:
        print(f"Error fetching current date and time from API: {e}")
        return None

def check_time_in_record_fingerprint(fingerprint_id):
    try:
        url = f"{RECENT_LOGS_FINGERPRINT_URL2}?fingerprint_id={fingerprint_id}"
        response = requests.get(url)
        response.raise_for_status()
        logs = response.json()
        return any(log.get('time_in') and not log.get('time_out') for log in logs)
    except requests.RequestException as e:
        print(f"Error checking Time-In record: {e}")
        return False


def record_time_in_fingerprint(fingerprint_id, user_name, role_id="2"):
    try:
        current_time_data = fetch_current_date_time()
        if not current_time_data:
            return
        url = f"{TIME_IN_FINGERPRINT_URL}?fingerprint_id={fingerprint_id}&time_in={current_time_data['current_time']}&user_name={user_name}&role_id={role_id}"
        response = requests.put(url)
        response.raise_for_status()
        result = response.json()
        print(result)
        messagebox.showinfo("Success", "Time-In recorded successfully.")
    except requests.RequestException as e:
        messagebox.showerror("Error", f"Error recording Time-In: {e}")


def record_time_out_fingerprint(fingerprint_id):
    try:
        current_time_data = fetch_current_date_time()
        if not current_time_data:
            return
        url = f"{TIME_OUT_FINGERPRINT_URL}?fingerprint_id={fingerprint_id}&time_out={current_time_data['current_time']}"
        response = requests.put(url)
        response.raise_for_status()
        result = response.json()
        print(result)
        print("Time-Out recorded successfully.")
    except requests.RequestException as e:
        print(f"Error recording Time-Out: {e}")


def record_time_in(rfid_number, user_name, year):
    try:
        current_time_data = fetch_current_date_time()
        if not current_time_data:
            return
        url = f"{TIME_IN_URL}?rfid_number={rfid_number}&time_in={current_time_data['current_time']}&year={year}&user_name={user_name}&role_id=3"
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
        current_time_data = fetch_current_date_time()
        if not current_time_data:
            return
        if not check_time_in_record(rfid_number):
            update_result("No Time-In record found for this RFID. Cannot record Time-Out.")
            return
        url = f"{TIME_OUT_URL}?rfid_number={rfid_number}&time_out={current_time_data['current_time']}"
        response = requests.put(url)
        response.raise_for_status()
        result = response.json()
        print(result)
        update_result("Time-Out recorded successfully.")
        fetch_recent_logs()
    except requests.RequestException as e:
        update_result(f"Error recording Time-Out: {e}")


def get_schedule(fingerprint_id):
    """Check if the current time is within the allowed schedule for the given fingerprint ID."""
    try:
        # Fetch current date and time from the API
        current_time_data = fetch_current_date_time()
        if not current_time_data:
            print("Error: Could not fetch current date and time from API.")
            return False

        # Extract the current day and time
        current_day = current_time_data.get('day_of_week')
        current_time = current_time_data.get('current_time')

        if not current_day or not current_time:
            print("Error: Invalid response from current date-time API.")
            return False

        print(f"Current Day from API: {current_day}, Current Time from API: {current_time}")

        # Fetch the lab schedule for the given fingerprint ID
        response = requests.get(f"{LAB_SCHEDULE_URL}{fingerprint_id}")
        response.raise_for_status()
        schedules = response.json()

        # Check if the current time is within any of the schedules for today
        for schedule in schedules:
            schedule_day = schedule.get('day_of_the_week')
            start_time = schedule.get('class_start')
            end_time = schedule.get('class_end')

            # Ensure all required fields are available
            if schedule_day and start_time and end_time:
                print(f"Checking Schedule: Day: {schedule_day}, Start: {start_time}, End: {end_time}")

                # Check if current day matches the schedule day
                if schedule_day == current_day:
                    # Compare current time with class start and end times
                    if start_time <= current_time <= end_time:
                        print("Access allowed based on schedule.")
                        return True  # Schedule matches, allow access

        print("Access denied: No matching schedule found or not within allowed time.")
        return False  # No matching schedule or not within allowed time
    except requests.RequestException as e:
        messagebox.showerror("Request Error", f"Failed to connect to API: {e}")
        return False

def auto_scan_fingerprint():
    global unlock_attempt

    if not finger:
        return

    print("Waiting for fingerprint image...")
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

    print("Detected fingerprint ID:", finger.finger_id, "with confidence", finger.confidence)

    # Fetch user details using API
    name = get_user_details(finger.finger_id)

    if name:
        if get_schedule(finger.finger_id):  # Check if the current time is within the allowed schedule
            if not check_time_in_record_fingerprint(finger.finger_id):
                # Record Time-In, unlock door, and transition to RFID scanning
                record_time_in_fingerprint(finger.finger_id, name)
                unlock_door()
                messagebox.showinfo("Welcome", f"Welcome, {name}! Door unlocked.")
                # Enable NFC scanning
                nfc_enabled.set()  # Allow NFC scanning to proceed
            else:
                # If a Time-In exists, record Time-Out and lock the door
                record_time_out_fingerprint(finger.finger_id)
                lock_door()
                messagebox.showinfo("Goodbye", f"Goodbye, {name}! Door locked.")
                # Stop NFC scanning as the session is complete
                nfc_enabled.clear()  # Ensure NFC scanning stops after a Time-Out
        else:
            messagebox.showinfo("No Access", "Access denied due to schedule restrictions.")
    else:
        messagebox.showinfo("No Match", "No matching fingerprint found in the database.")

    # Continue scanning fingerprints after processing
    root.after(5000, auto_scan_fingerprint)  # Restart fingerprint scanning after NFC loop

# Initialize NFC frontend
try:
    clf = nfc.ContactlessFrontend('usb')
except Exception as e:
    messagebox.showerror("NFC Error", f"Failed to initialize NFC reader: {e}")
    clf = None


def fetch_recent_logs():
    try:
        response = requests.get(RECENT_LOGS_URL)
        response.raise_for_status()
        logs = response.json()
        for i in logs_tree.get_children():
            logs_tree.delete(i)
        for log in logs:
            logs_tree.insert("", "end", values=(
                log.get('date', 'N/A'),
                log.get('user_name', 'N/A'),
                log.get('pc_name', 'N/A'),
                log.get('student_number', 'N/A'),
                log.get('year', 'N/A'),
                log.get('section', 'N/A'),
                log.get('faculty', 'N/A'),
                log.get('time_in', 'N/A'),
                log.get('time_out', 'N/A')
            ))
    except requests.RequestException as e:
        update_result(f"Error fetching recent logs: {e}")


def fetch_user_info(uid):
    try:
        url = f'{USER_INFO_URL}?id_card_id={uid}'
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        student_number_entry.delete(0, tk.END)
        student_number_entry.insert(0, data.get('user_number', 'None'))

        name_entry.delete(0, tk.END)
        name_entry.insert(0, data.get('user_name', 'None'))

        year_entry.delete(0, tk.END)
        year_entry.insert(0, data.get('year', 'None'))

        section_entry.delete(0, tk.END)
        section_entry.insert(0, data.get('block', 'None'))

        error_label.config(text="")

        if check_time_in_record(uid):
            record_time_out(uid)
        else:
            record_time_in(uid, data.get('user_name', 'None'), data.get('year', 'None'))

    except requests.HTTPError as http_err:
        if response.status_code == 404:
            clear_data()
            update_result("Card is not registered, Please contact the administrator.")
        else:
            update_result(f"HTTP error occurred: {http_err}")
    except requests.RequestException as e:
        update_result(f"Error fetching user info: {e}")


def check_time_in_record(rfid_number):
    try:
        url = f'{RECENT_LOGS_URL2}?rfid_number={rfid_number}'
        response = requests.get(url)
        response.raise_for_status()
        logs = response.json()
        return any(log.get('time_in') and not log.get('time_out') for log in logs)
    except requests.RequestException as e:
        update_result(f"Error checking Time-In record: {e}")
        return False


def clear_data():
    student_number_entry.delete(0, tk.END)
    name_entry.delete(0, tk.END)
    year_entry.delete(0, tk.END)
    section_entry.delete(0, tk.END)
    error_label.config(text="")


def update_result(message):
    error_label.config(text=message)


def read_nfc_loop():
    def on_connect(tag):
        uid = tag.identifier.hex()
        fetch_user_info(uid)  # This function handles time-in and time-out based on RFID scans
        return True

    try:
        while True:
            # Wait for the event triggered by fingerprint match
            nfc_enabled.wait()  # Ensure NFC scanning starts only when enabled

            if clf and nfc_enabled.is_set():
                try:
                    clf.connect(rdwr={'on-connect': on_connect})
                except Exception as e:
                    print(f"NFC read error: {e}")
                    time.sleep(1)  # Delay to prevent excessive error logging

            # Add a small delay to avoid busy-waiting
            time.sleep(0.1)
    except Exception as e:
        print(f"NFC Loop Error: {e}")

# Create the main Tkinter window
root = tk.Tk()
root.title("Fingerprint and NFC Reader")
root.geometry("1200x800")

# Real-time date and time display
time_frame = ttk.Frame(root, padding="10")
time_frame.pack(side="top", fill="x")
time_label = ttk.Label(time_frame, text="", font=("Arial", 14))
time_label.pack()


def update_time():
    fetch_current_date_time()  # Fetch and update the current date and time from the API
    root.after(10000, update_time)  # Update every 10 seconds


update_time()

# Top frame for fingerprint and NFC
top_frame = ttk.Frame(root, padding="10")
top_frame.pack(side="top", fill="x")

# Fingerprint frame
left_frame = ttk.Frame(top_frame, padding="10")
left_frame.pack(side="left", fill="y", expand=True)
fingerprint_label = ttk.Label(left_frame, text="Fingerprint Sensor", font=("Arial", 16))
fingerprint_label.pack(pady=20)

# NFC frame
right_frame = ttk.Frame(top_frame, padding="10")
right_frame.pack(side="right", fill="y", expand=True)

# Student Number, Name, Year, Section labels and entries
student_number_label = ttk.Label(right_frame, text="Student Number:", font=("Arial", 14))
student_number_label.pack(pady=5)
student_number_entry = ttk.Entry(right_frame, font=("Arial", 14))
student_number_entry.pack(pady=5)

name_label = ttk.Label(right_frame, text="Name:", font=("Arial", 14))
name_label.pack(pady=5)
name_entry = ttk.Entry(right_frame, font=("Arial", 14))
name_entry.pack(pady=5)

year_label = ttk.Label(right_frame, text="Year:", font=("Arial", 14))
year_label.pack(pady=5)
year_entry = ttk.Entry(right_frame, font=("Arial", 14))
year_entry.pack(pady=5)

section_label = ttk.Label(right_frame, text="Section:", font=("Arial", 14))
section_label.pack(pady=5)
section_entry = ttk.Entry(right_frame, font=("Arial", 14))
section_entry.pack(pady=5)

# Error Message Label
error_label = tk.Label(root, text="", font=("Helvetica", 10, "bold", "italic"), foreground="red")
error_label.pack(pady=10)

# Logs Table
table_frame = ttk.Frame(root, padding="10")
table_frame.pack(side="bottom", fill="both", expand=True)
columns = ("Date", "Name", "PC", "Student Number", "Year", "Section", "Faculty", "Time-in", "Time-out")
logs_tree = ttk.Treeview(table_frame, columns=columns, show='headings')
logs_tree.pack(pady=10, fill='both', expand=True)
for col in columns:
    logs_tree.heading(col, text=col)
    logs_tree.column(col, minwidth=100, width=100, anchor='center')

# Start fingerprint and NFC threads
fingerprint_thread = threading.Thread(target=auto_scan_fingerprint)
nfc_thread = threading.Thread(target=read_nfc_loop)
fingerprint_thread.start()
nfc_thread.start()


# Ensure threads are cleaned up properly
def on_closing():
    global running
    running = False
    if fingerprint_thread.is_alive():
        fingerprint_thread.join()
    if nfc_thread.is_alive():
        nfc_thread.join()
    if clf is not None:
        clf.close()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_closing)

# Fetch and display recent logs
fetch_recent_logs()

# Start the Tkinter main loop
root.mainloop()
