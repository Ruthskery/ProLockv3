import subprocess
import time
import os
import nfc

def detect_uid():
    # Detect the UID using nfcpy
    clf = nfc.ContactlessFrontend('usb')
    tag = clf.connect(rdwr={'on-connect': lambda tag: False})
    if tag:
        return tag.identifier.hex().upper()
    return None

def main():
    while True:
        uid = detect_uid()
        if uid:
            print(f"UID Detected: {uid}")
            # Start 2.py
            p = subprocess.Popen(['python', '2.py'], shell=True)
            
            # Wait for 10 seconds
            time.sleep(10)

            # If 2.py is still running, terminate it
            if p.poll() is None:
                p.terminate()
            
            # Restart 1.py
            print("Returning to UID scanning...")
            continue  # Continue the loop to keep scanning
        time.sleep(1)  # Check for UID every 1 second

if __name__ == "__main__":
    main()
