import threading
import time
import serial
import adafruit_fingerprint
import nfc
import tkinter as tk
from tkinter import ttk
from datetime import datetime

# Global flag to control NFC activation
nfc_enabled = threading.Event()

# Initialize the fingerprint sensor
def fingerprint_task(fingerprint_status):
    uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)  # Update with your port
    fingerprint = adafruit_fingerprint.Adafruit_Fingerprint(uart)

    while True:
        try:
            fingerprint_status.set("Waiting for finger...")

            # Check if a finger is detected
            if fingerprint.get_image() == adafruit_fingerprint.OK:
                fingerprint_status.set("Finger detected, processing...")

                if fingerprint.image_2_tz(1) != adafruit_fingerprint.OK:
                    fingerprint_status.set("Failed to convert image to template")
                    continue

                # Search for a match in the database
                if fingerprint.finger_search() == adafruit_fingerprint.OK:
                    fingerprint_status.set(f"Match found! ID: {fingerprint.finger_id}, Confidence: {fingerprint.confidence}")
                    nfc_enabled.set()  # Enable NFC reader after a successful fingerprint match
                else:
                    fingerprint_status.set("No match found")

            time.sleep(1)

        except Exception as e:
            fingerprint_status.set(f"Error: {e}")

# Initialize the NFC reader
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
    current_time = now.strftime("%A %d %B %Y %H:%M")
    time_label.config(text=f"Current Date and Time: {current_time}")
    root.after(1000, update_time)  # Update every second

# Create the main Tkinter window
root = tk.Tk()
root.title("Fingerprint and NFC Reader")

# Set up the layout
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
fingerprint_thread = threading.Thread(target=fingerprint_task, args=(fingerprint_status,))
nfc_thread = threading.Thread(target=nfc_task, args=(nfc_status, uid_display))

fingerprint_thread.start()
nfc_thread.start()

# Start the real-time clock update
update_time()

# Start the Tkinter main loop
root.mainloop()

# Ensure threads are cleaned up properly
fingerprint_thread.join()
nfc_thread.join()
