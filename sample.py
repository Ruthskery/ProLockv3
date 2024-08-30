import tkinter as tk
import os
import time
import nfc
import subprocess

def detect_uid():
    # Detect the UID using nfcpy
    try:
        clf = nfc.ContactlessFrontend('usb')
        tag = clf.connect(rdwr={'on-connect': lambda tag: False})
        if tag:
            return tag.identifier.hex().upper()
    except Exception as e:
        print(f"Error in detect_uid: {e}")
    return None

def main():
    root = tk.Tk()
    root.title("2.py - NFC UID Detection")
    root.geometry("400x200")

    label = tk.Label(root, text="Waiting for UID...", font=("Arial", 14))
    label.pack(pady=50)

    start_time = time.time()  # Track the start time

    def on_timeout():
        print("5 seconds passed without UID detection. Closing window and restarting 1.py...")
        root.quit()  # Stop the Tkinter main loop
        root.destroy()  # Destroy the window

        # Use the absolute path to 1.py if it's not in the same directory
        command = ['python', '1.py']  # Use full path if necessary
        print(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)
        print(f"Command output: {result.stdout}")  # Print the output of the command
        print(f"Command error: {result.stderr}")   # Print any error from the command

    def check_uid():
        nonlocal start_time
        uid = detect_uid()
        if uid:
            print(f"UID Detected in 2.py: {uid}")
            label.config(text=f"UID Detected: {uid}")
            start_time = time.time()  # Reset the start time on UID detection
        elif time.time() - start_time > 5:  # 5-second timeout
            on_timeout()  # Close window and restart 1.py
        else:
            root.after(1000, check_uid)  # Check for UID every 1 second

    # Start checking for UID after 1 second
    root.after(1000, check_uid)
    root.mainloop()

if __name__ == "__main__":
    main()
