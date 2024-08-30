1.py

import subprocess
import time
import os

def detect_uid():
    # Placeholder function to detect UID from the ACR122U
    # Replace this with actual code to read UID
    uid = "example_uid"
    return uid

def main():
    while True:
        uid = detect_uid()
        if uid:
            print(f"UID Detected: {uid}")
            # Terminate 1.py and start 2.py
            subprocess.Popen(['python', '2.py'], shell=True)
            os._exit(0)
        time.sleep(1)  # Check for UID every 1 second

if __name__ == "__main__":
    main()


2.py
import time
import os

def re_read_uid():
    # Placeholder function to re-read UID
    # Replace this with actual code to re-read UID
    uid = "example_uid"
    return uid

def main():
    start_time = time.time()
    while True:
        uid = re_read_uid()
        if uid:
            print(f"UID Re-read: {uid}")
            # UID read successfully, perform further actions if needed
            start_time = time.time()  # Reset the timer
        time_elapsed = time.time() - start_time
        if time_elapsed > 10:
            print("No UID detected for 10 seconds. Restarting 1.py...")
            os.system('python 1.py')
            os._exit(0)
        time.sleep(1)  # Check for UID every 1 second

if __name__ == "__main__":
    main()
