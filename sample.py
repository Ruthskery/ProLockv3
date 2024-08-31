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
        url = f"{TIME_OUT_FINGERPRINT_URL}?fingerprint_id={fingerprint_id}&time_out={datetime.now().strftime('%H:%M')}"
        response = requests.put(url)
        response.raise_for_status()
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
                today = datetime.now().strftime('%A')
                current_time = datetime.now().strftime('%H:%M')
                for schedule in schedules:
                    if schedule['day_of_the_week'] == today:
                        start_time = schedule['class_start']
                        end_time = schedule['class_end']
                        if start_time <= current_time <= end_time:
                            return True
            return False
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
        if get_schedule(finger.finger_id):
            if not check_time_in_record_fingerprint(finger.finger_id):
                record_time_in_fingerprint(finger.finger_id, name)
                unlock_door()
                messagebox.showinfo("Welcome", f"Welcome, {name}! Door unlocked.")
                nfc_enabled.set()  # Enable NFC reader after a successful fingerprint match
                root.after(5000, lock_door)  # Lock the door after 5 seconds
            else:
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
        response.raise_for_status()
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

        error_label.config(text="")

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
        return any(log.get('time_in') and not log.get('time_out') for log in logs)
    except requests.RequestException as e:
        messagebox.showerror("Error", f"Error checking time-in record: {e}")
        return False

def record_time_in(uid, name, year):
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        response = requests.post(TIME_IN_URL, json={'uid': uid, 'time_in': now, 'user_name': name})
        response.raise_for_status()
        messagebox.showinfo("Success", "Time-In recorded successfully.")
    except requests.RequestException as e:
        messagebox.showerror("Error", f"Error recording time-in: {e}")

def record_time_out(uid):
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        response = requests.post(TIME_OUT_URL, json={'uid': uid, 'time_out': now})
        response.raise_for_status()
        messagebox.showinfo("Success", "Time-Out recorded successfully.")
    except requests.RequestException as e:
        messagebox.showerror("Error", f"Error recording time-out: {e}")

def clear_data():
    student_number_entry.delete(0, tk.END)
    name_entry.delete(0, tk.END)
    year_entry.delete(0, tk.END)
    section_entry.delete(0, tk.END)

def update_result(message):
    error_label.config(text=message)

# Initialize the NFC reader
def init_nfc_reader():
    try:
        clf = nfc.ContactlessFrontend('usb')
        return clf
    except Exception as e:
        messagebox.showerror("NFC Error", f"Failed to initialize NFC reader: {e}")
        return None

def scan_nfc():
    clf = init_nfc_reader()
    if clf:
        while running:
            tag = clf.poll()
            if tag:
                uid = tag.identifier
                uid_str = ''.join([f"{byte:02X}" for byte in uid])
                fetch_user_info(uid_str)
                time.sleep(1)  # Prevent continuous scanning

# GUI Setup
def setup_gui():
    global root
    root.title("Fingerprint and NFC Reader")

    # Create and place widgets
    ttk.Label(root, text="Student Number:").grid(row=0, column=0, padx=10, pady=10)
    global student_number_entry
    student_number_entry = ttk.Entry(root)
    student_number_entry.grid(row=0, column=1, padx=10, pady=10)

    ttk.Label(root, text="Name:").grid(row=1, column=0, padx=10, pady=10)
    global name_entry
    name_entry = ttk.Entry(root)
    name_entry.grid(row=1, column=1, padx=10, pady=10)

    ttk.Label(root, text="Year:").grid(row=2, column=0, padx=10, pady=10)
    global year_entry
    year_entry = ttk.Entry(root)
    year_entry.grid(row=2, column=1, padx=10, pady=10)

    ttk.Label(root, text="Section:").grid(row=3, column=0, padx=10, pady=10)
    global section_entry
    section_entry = ttk.Entry(root)
    section_entry.grid(row=3, column=1, padx=10, pady=10)

    global error_label
    error_label = ttk.Label(root, text="", foreground="red")
    error_label.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

    # Start fingerprint scanning in a separate thread
    threading.Thread(target=auto_scan_fingerprint, daemon=True).start()

    # Start NFC scanning in a separate thread
    threading.Thread(target=scan_nfc, daemon=True).start()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

def on_closing():
    global running
    running = False
    GPIO.cleanup()  # Cleanup GPIO
    root.destroy()

if __name__ == "__main__":
    setup_gui()
