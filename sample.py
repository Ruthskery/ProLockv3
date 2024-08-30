import tkinter as tk
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
    root = tk.Tk()
    root.title("NFC UID Detection")
    root.geometry("400x200")

    label = tk.Label(root, text="Please scan your NFC card...", font=("Arial", 14))
    label.pack(pady=50)

    def check_nfc():
        uid = detect_uid()
        if uid:
            print(f"UID Detected: {uid}")
            label.config(text=f"UID Detected: {uid}")
            # Reset label to ask for scanning again after 2 seconds
            root.after(2000, lambda: label.config(text="Please scan your NFC card..."))
        else:
            print("No NFC card detected. Waiting for scan...")
            label.config(text="Please scan your NFC card...")

        # Continue checking for NFC every 1 second
        root.after(1000, check_nfc)

    # Start the NFC check loop
    check_nfc()

    root.mainloop()

if __name__ == "__main__":
    main()
