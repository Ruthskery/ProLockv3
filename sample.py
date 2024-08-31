
import tkinter as tk
from tkinter import font, ttk
from datetime import datetime
import nfc
import threading
import time
import requests

# Replace these URLs with your actual Laravel API URLs
USER_INFO_URL = 'https://prolocklogger.pro/api/user-information/by-id-card'
RECENT_LOGS_URL = 'https://prolocklogger.pro/api/recent-logs'
TIME_IN_URL = 'https://prolocklogger.pro/api/logs/time-in'
TIME_OUT_URL = 'https://prolocklogger.pro/api/logs/time-out'
RECENT_LOGS_URL2 = 'https://prolocklogger.pro/api/recent-logs/by-uid'

root = tk.Tk()
root.title("RFID Scanning and Attendance")
root.geometry("1200x500")  # Adjust window size

# Define custom fonts
heading_font = font.Font(family="Helvetica", size=16, weight="bold")
label_font = font.Font(family="Helvetica", size=12)
clock_font = font.Font(family="Helvetica", size=14)

# Function to update the clock
clock_label = tk.Label(root, font=clock_font)
clock_label.pack(pady=10)

def update_clock():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clock_label.config(text=current_time)
    root.after(1000, update_clock)  # Update every 1 second

update_clock()  # Initialize the clock

# Create the main heading
main_heading = tk.Label(root, text="Student Attendance Monitoring", font=heading_font)
main_heading.pack(pady=10)

# Student Information Frame
info_frame = tk.Frame(root)
info_frame.pack(pady=10)

# Student Number
student_number_label = tk.Label(info_frame, text="Student Number:", font=label_font)
student_number_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')
student_number_entry = tk.Entry(info_frame, font=label_font)
student_number_entry.grid(row=0, column=1, padx=10, pady=5)

# Name
name_label = tk.Label(info_frame, text="Name:", font=label_font)
name_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')
name_entry = tk.Entry(info_frame, font=label_font)
name_entry.grid(row=1, column=1, padx=10, pady=5)

# Year
year_label = tk.Label(info_frame, text="Year:", font=label_font)
year_label.grid(row=2, column=0, padx=10, pady=5, sticky='w')
year_entry = tk.Entry(info_frame, font=label_font)
year_entry.grid(row=2, column=1, padx=10, pady=5)

# Section
section_label = tk.Label(info_frame, text="Section:", font=label_font)
section_label.grid(row=3, column=0, padx=10, pady=5, sticky='w')
section_entry = tk.Entry(info_frame, font=label_font)
section_entry.grid(row=3, column=1, padx=10, pady=5)

# Error Message Label
error_label = tk.Label(root, text="", font=("Helvetica", 10, "bold", "italic"), foreground="red")
error_label.pack(pady=10)

# Create the Treeview for logs with new columns
columns = ("Date", "Name", "PC", "Student Number", "Year", "Section", "Faculty", "Time-in", "Time-out")
logs_tree = ttk.Treeview(root, columns=columns, show='headings')
logs_tree.pack(pady=10, fill='both', expand=True)

# Define column headings
for col in columns:
    logs_tree.heading(col, text=col)
    logs_tree.column(col, minwidth=100, width=100, anchor='center')

clf = nfc.ContactlessFrontend('usb')
running = True

time_in_records = set()
time_out_records = set()

def fetch_recent_logs():
    try:
        response = requests.get(RECENT_LOGS_URL)
        response.raise_for_status()

        logs = response.json()

        # Clear existing logs
        for i in logs_tree.get_children():
            logs_tree.delete(i)

        # Insert new logs
        for log in logs:
            logs_tree.insert("", "end", values=(
                log.get('date', 'N/A'),
                log.get('user_name', 'N/A'),
                log.get('pc_name', 'N/A'),  # Assuming 'PC' refers to a field called 'pc_name'
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

def clear_data():
    # Clear all entry fields
    student_number_entry.delete(0, tk.END)
    name_entry.delete(0, tk.END)
    year_entry.delete(0, tk.END)
    section_entry.delete(0, tk.END)

def update_result(message):
    error_label.config(text=message)

def read_nfc_loop():
    global running
    while running:
        try:
            tag = clf.connect(rdwr={'on-connect': lambda tag: False})
            if tag:
                uid = tag.identifier.hex()
                fetch_user_info(uid)
                time.sleep(1)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

def on_closing():
    global running
    running = False
    if thread.is_alive():
        thread.join()
    if clf is not None:
        clf.close()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# Fetch and display recent logs
fetch_recent_logs()

# Start NFC reader thread
thread = threading.Thread(target=read_nfc_loop)
thread.start()

# Run the application
root.mainloop()

