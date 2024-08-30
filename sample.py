import tkinter as tk
import os
import time
import nfc

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
    global timeout_timer  # Declare timeout_timer as global at the start of the function

    root = tk.Tk()
    root.title("2.py - NFC UID Detection")
    root.geometry("400x200")

    label = tk.Label(root, text="Waiting for UID or timer to restart...", font=("Arial", 14))
    label.pack(pady=50)

    start_time = time.time()  # Track the start time for NFC detection
    timeout_duration = 10  # Timeout duration in seconds

    def on_timeout():
        print("10 seconds passed. Closing window and restarting 1.py...")
        root.quit()  # Stop the Tkinter main loop
        root.destroy()  # Destroy the window
        os.system('python 1.py')  # Restart 1.py

    def check_nfc():
        nonlocal start_time
        uid = detect_uid()
        if uid:
            print(f"UID Detected in 2.py: {uid}")
            label.config(text=f"UID Detected: {uid}")
            start_time = time.time()  # Reset the start time on UID detection
            
            # Reset the timeout timer
            global timeout_timer
            if 'timeout_timer' in globals():
                root.after_cancel(timeout_timer)  # Cancel any previous timeout timer
            timeout_timer = root.after(timeout_duration * 1000, on_timeout)  # Set a new timeout timer
        else:
            # Check if the timeout has elapsed
            if time.time() - start_time > timeout_duration:
                on_timeout()  # Close window and restart 1.py
            else:
                root.after(1000, check_nfc)  # Check for UID every 1 second

    # Initialize timeout timer
    timeout_timer = root.after(timeout_duration * 1000, on_timeout)

    # Start checking for UID after 1 second
    root.after(1000, check_nfc)

    root.mainloop()

if __name__ == "__main__":
    main()

