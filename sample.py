import tkinter as tk
from tkinter import ttk
from datetime import datetime
import threading
import time
from fingerprint_task import (
    auto_scan_fingerprint, unlock_door, lock_door, get_user_details, check_time_in_record, record_time_in, record_time_out, get_schedule, center_widget
)
import nfc_task

# Initialize global variables
nfc_enabled = threading.Event()

# Function to update the real-time date and time display
def update_time():
    now = datetime.now()
    current_time = now.strftime("%A %d %B %Y %H:%M")
    time_label.config(text=f"Current Date and Time: {current_time}")
    root.after(1000, update_time)  # Update every second

# Function to add an entry to the table
def add_table_entry(date, name, pc, student_number, year, section, faculty, time_in, time_out):
    table.insert("", "end", values=(date, name, pc, student_number, year, section, faculty, time_in, time_out))

# Create the main Tkinter window
root = tk.Tk()
root.title("Fingerprint and NFC Reader")
root.geometry("1280x500")

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

fingerprint_status = tk.StringVar()
fingerprint_status_label = ttk.Label(left_frame, textvariable=fingerprint_status, wraplength=250)
fingerprint_status_label.pack()

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
fingerprint_thread = threading.Thread(target=fingerprint_task.fingerprint_task, args=(fingerprint_status, nfc_enabled, add_table_entry,))
nfc_thread = threading.Thread(target=nfc_task.nfc_task, args=(nfc_status, uid_display, nfc_enabled,))

fingerprint_thread.start()
nfc_thread.start()

# Start the real-time clock update
update_time()

# Start the Tkinter main loop
root.mainloop()

# Ensure threads are cleaned up properly
fingerprint_thread.join()
nfc_thread.join()
