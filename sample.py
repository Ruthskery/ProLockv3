import time
import nfc
import tkinter as tk
import os

def detect_uid():
    # Detect the UID using nfcpy
    clf = nfc.ContactlessFrontend('usb')
    tag = clf.connect(rdwr={'on-connect': lambda tag: False})
    if tag:
        return tag.identifier.hex().upper()
    return None

def main():
    root = tk.Tk()
    root.title("2.py - Re-read NFC UID")
    root.geometry("400x200")
    
    label = tk.Label(root, text="Waiting for UID...", font=("Arial", 14))
    label.pack(pady=50)
    
    start_time = time.time()  # Track the start time

    def check_uid():
        uid = detect_uid()
        if uid:
            print(f"UID Detected in 2.py: {uid}")
            label.config(text=f"UID Detected: {uid}")
            start_time = time.time()  # Reset the start time on UID detection
        elif time.time() - start_time > 5:  # 5-second timeout
            root.quit()  # Stop the Tkinter main loop
            root.destroy()  # Destroy the window
            os.system('python 1.py')  # Restart 1.py
        else:
            root.after(1000, check_uid)  # Check for UID every 1 second
    
    root.after(1000, check_uid)  # Start checking for UID after 1 second
    root.mainloop()

if __name__ == "__main__":
    main()
