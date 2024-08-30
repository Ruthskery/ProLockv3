import tkinter as tk
import os
import time
import nfc

def detect_uid():
    try:
        clf = nfc.ContactlessFrontend('usb')
        tag = clf.connect(rdwr={'on-connect': lambda tag: False})
        if tag:
            return tag.identifier.hex().upper()
    except Exception as e:
        print(f"Error in detect_uid: {e}")
    return None

def main():
    global timeout_timer

    root = tk.Tk()
    root.title("2.py - NFC UID Detection")
    root.geometry("400x200")

    label = tk.Label(root, text="Waiting for UID or timer to restart...", font=("Arial", 14))
    label.pack(pady=50)

    timeout_duration = 10  # Timeout duration in seconds

    def on_timeout():
        print("10 seconds passed. Closing window and restarting 1.py...")
        root.quit()
        root.destroy()
        os.system('python 1.py')

    def reset_timeout():
        global timeout_timer
        if 'timeout_timer' in globals():
            root.after_cancel(timeout_timer)
        timeout_timer = root.after(timeout_duration * 1000, on_timeout)

    def check_nfc():
        uid = detect_uid()
        if uid:
            print(f"UID Detected in 2.py: {uid}")
            label.config(text=f"UID Detected: {uid}")
            reset_timeout()  # Reset the timeout timer
        else:
            print("No UID Detected in 2.py")
            label.config(text="No UID Detected")

        # Continue scanning regardless of UID detection
        root.after(1000, check_nfc)

    # Initialize timeout timer
    reset_timeout()

    # Start checking for UID after 1 second
    root.after(1000, check_nfc)

    root.mainloop()

if __name__ == "__main__":
    main()
