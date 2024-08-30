import subprocess
import time
import os
import nfc
import tkinter as tk

def detect_uid():
    # Detect the UID using nfcpy
    clf = nfc.ContactlessFrontend('usb')
    tag = clf.connect(rdwr={'on-connect': lambda tag: False})
    if tag:
        return tag.identifier.hex().upper()
    return None

def main():
    root = tk.Tk()
    root.title("1.py - NFC UID Scanner")
    root.geometry("400x200")
    
    label = tk.Label(root, text="Place your NFC card on the reader...", font=("Arial", 14))
    label.pack(pady=50)
    
    def check_uid():
        uid = detect_uid()
        if uid:
            print(f"UID Detected: {uid}")
            # Terminate 1.py and start 2.py
            root.quit()  # Stop the Tkinter mainloop
            root.destroy()  # Destroy the window
            subprocess.Popen(['python', '2.py'], shell=True)
        else:
            root.after(1000, check_uid)  # Check for UID every 1 second
    
    root.after(1000, check_uid)  # Start checking for UID after 1 second
    root.mainloop()

if __name__ == "__main__":
    main()

