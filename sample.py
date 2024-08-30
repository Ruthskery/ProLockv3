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
    global timeout_timer  # Declare timeout_timer as global

    root = tk.Tk()
    root.title("2.py - NFC UID Detection")
    root.geometry("400x200")

    label = tk.Label(root, text="Waiting for UID or timer to restart...", font=("Arial", 14))
    label.pack(pady=50)

    timeout_duration = 10  # Timeout duration in seconds

    def on_timeout():
        print("10 seconds passed. Closing window and restarting 1.py...")
        root.quit()  # Stop the Tkinter main loop
        root.destroy()  # Destroy the window
        
        # Restart 1.py with full path and log output
        command = 'python /full/path/to/1.py > restart_log.txt 2>&1'
        os.system(command)

    def reset_timeout():
        global timeout_timer
        if 'timeout_timer' in globals():
            root.after_cancel(timeout_timer)  # Cancel any previous timeout timer
        timeout_timer = root.after(timeout_duration * 1000, on_timeout)  # Set a new timeout timer

    def check_nfc():
        uid = detect_uid()
        if uid:
            print(f"UID Detected in 2.py: {uid}")
            label.config(text=f"UID Detected: {uid}")
            reset_timeout()  # Reset the timeout timer on UID detection
        else:
            print("No UID Detected in 2.py")
            label.config(text="No UID Detected")
        
        # Continue scanning regardless of UID detection
        root.after(1000, check_nfc)  # Check for UID every 1 second

    # Initialize timeout timer
    reset_timeout()

    # Start checking for UID after 1 second
    root.after(1000, check_nfc)

    root.mainloop()

if __name__ == "__main__":
    main()
