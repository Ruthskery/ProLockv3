import threading
import time
from pyfingerprint.pyfingerprint import PyFingerprint
import nfc

# Initialize the fingerprint sensor
def fingerprint_task():
    try:
        # Initialize the fingerprint sensor
        f = PyFingerprint('/dev/ttyUSB0', 57600)  # Update with your port and baud rate
        
        print("Fingerprint sensor initialized")
        
        while True:
            try:
                print("Waiting for finger...")
                
                # Wait for a finger to be placed
                while not f.readImage():
                    pass
                
                # Convert the image to a template
                f.convertImage(0x01)
                
                # Check if the finger is already enrolled
                if f.searchTemplate()[0] == -1:
                    print("Finger not found")
                else:
                    print("Finger found")
                
            except Exception as e:
                print("Error:", e)
                
            time.sleep(1)  # Poll every second

    except Exception as e:
        print("Error initializing fingerprint sensor:", e)

# Initialize the NFC reader
def nfc_task():
    def on_connect(tag):
        print("NFC Tag detected:", tag)
        
    try:
        clf = nfc.ContactlessFrontend('usb')
        
        print("NFC reader initialized")
        
        while True:
            clf.connect(rdwr={'on-connect': on_connect})
            
            time.sleep(1)  # Poll every second

    except Exception as e:
        print("Error initializing NFC reader:", e)

# Create and start threads
fingerprint_thread = threading.Thread(target=fingerprint_task)
nfc_thread = threading.Thread(target=nfc_task)

fingerprint_thread.start()
nfc_thread.start()

# Join threads to keep the script running
fingerprint_thread.join()
nfc_thread.join()
