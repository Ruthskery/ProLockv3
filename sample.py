import threading
import time
import serial
import adafruit_fingerprint
import nfc

# Initialize the fingerprint sensor
def fingerprint_task():
    # Initialize the serial connection to the fingerprint sensor
    uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)  # Update with your port

    # Create a Fingerprint object
    fingerprint = adafruit_fingerprint.Adafruit_Fingerprint(uart)

    print("Fingerprint sensor initialized")

    while True:
        try:
            print("Waiting for finger...")

            # Check if a finger is detected
            if fingerprint.get_image() == adafruit_fingerprint.OK:
                print("Finger detected, processing...")

                if fingerprint.image_2_tz(1) != adafruit_fingerprint.OK:
                    print("Failed to convert image to template")
                    continue

                # Search for a match in the database
                if fingerprint.finger_search() == adafruit_fingerprint.OK:
                    print(f"Found fingerprint! ID: {fingerprint.finger_id}, Confidence: {fingerprint.confidence}")
                else:
                    print("No match found")

            time.sleep(1)  # Poll every second

        except Exception as e:
            print("Error:", e)

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
