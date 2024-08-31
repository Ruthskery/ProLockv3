import threading
import time
import serial
import adafruit_fingerprint
import nfc
import tkinter as tk
from tkinter import ttk

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
def nfc_task(nfc_status):
    def on_connect(tag):
        # Extract and display the UID of the NFC tag
        uid = tag.identifier.hex().upper()
        nfc_status.set(f"NFC Tag detected! UID: {uid}")

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

# Create the main Tkinter window
root = tk.Tk()
root.title("Fingerprint and NFC Reader")

# Set up the layout
root.geometry("600x400")

# Create a frame for the fingerprint sensor on the left
left_frame = ttk.Frame(root, padding="10")
left_frame.pack(side="left", fill="both", expand=True)

fingerprint_label = ttk.Label(left_frame, text="Fingerprint Sensor", font=("Arial", 16))
fingerprint_label.pack(pady=20)

fingerprint_status = tk.StringVar()
fingerprint_status_label = ttk.Label(left_frame, textvariable=fingerprint_status, wraplength=250)
fingerprint_status_label.pack()

# Create a frame for the NFC reader on the right
right_frame = ttk.Frame(root, padding="10")
right_frame.pack(side="right", fill="both", expand=True)

nfc_label = ttk.Label(right_frame, text="NFC Reader", font=("Arial", 16))
nfc_label.pack(pady=20)

nfc_status = tk.StringVar()
nfc_status_label = ttk.Label(right_frame, textvariable=nfc_status, wraplength=250)
nfc_status_label.pack()

# Start the fingerprint and NFC tasks in separate threads
fingerprint_thread = threading.Thread(target=fingerprint_task, args=(fingerprint_status,))
nfc_thread = threading.Thread(target=nfc_task, args=(nfc_status,))

fingerprint_thread.start()
nfc_thread.start()

# Start the Tkinter main loop
root.mainloop()

# Ensure threads are cleaned up properly
fingerprint_thread.join()
nfc_thread.join()
