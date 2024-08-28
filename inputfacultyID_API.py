import tkinter as tk
from tkinter import messagebox, ttk, font
import requests
import time
import serial
import adafruit_fingerprint

# Laravel API endpoint URLs
API_URL = 'https://prolocklogger.pro/api'
FACULTIES_URL = f'{API_URL}/users/role/2'
ENROLL_URL = f'{API_URL}/users/update-fingerprint'

# Initialize serial connection for the fingerprint sensor
uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

def fetch_faculty_data():
    """Fetch faculty data from the Laravel API, excluding those with registered fingerprint IDs."""
    try:
        response = requests.get(FACULTIES_URL)
        response.raise_for_status()
        data = response.json()
        print("API Response:", data)  # Debug: print API response
        
        # Filter out faculty members who already have a registered fingerprint ID
        filtered_data = [faculty for faculty in data if not faculty.get('fingerprint_id')]
        
        return filtered_data
    except requests.RequestException as e:
        messagebox.showerror("Error", f"Error fetching faculty data: {e}")
        return []

def post_fingerprint(email, fingerprint_id):
    """Post fingerprint data to the Laravel API."""
    try:
        # Build the URL with query parameters
        url = f"{ENROLL_URL}?email={email}&fingerprint_id={fingerprint_id}"
        
        print(url)
        
        # Send the POST request
        response = requests.put(url)
        response.raise_for_status()  # Raise an error for bad responses (4xx and 5xx)

        # Notify success
        messagebox.showinfo("Success", "Fingerprint enrolled successfully")
    except requests.RequestException as e:
        # Notify failure
        messagebox.showerror("Error", f"Error posting fingerprint data: {e}")

def enroll_fingerprint(email, fingerprint_id):
    """Enroll a fingerprint and prepare it for posting."""
    try:
        # Convert fingerprint_id to integer if it is not already an integer
        fingerprint_id_int = int(fingerprint_id)
    except ValueError:
        print("Invalid fingerprint ID. It must be an integer.")
        return False

    for fingerimg in range(1, 3):
        if fingerimg == 1:
            print("Place finger on sensor...", end="")
        else:
            print("Place same finger again...", end="")

        while True:
            i = finger.get_image()
            if i == adafruit_fingerprint.OK:
                print("Image taken")
                break
            if i == adafruit_fingerprint.NOFINGER:
                print(".", end="")
            elif i == adafruit_fingerprint.IMAGEFAIL:
                print("Imaging error")
                return False
            else:
                print("Other error")
                return False

        print("Templating...", end="")
        i = finger.image_2_tz(fingerimg)
        if i == adafruit_fingerprint.OK:
            print("Templated")
        else:
            if i == adafruit_fingerprint.IMAGEMESS:
                print("Image too messy")
            elif i == adafruit_fingerprint.FEATUREFAIL:
                print("Could not identify features")
            elif i == adafruit_fingerprint.INVALIDIMAGE:
                print("Image invalid")
            else:
                print("Other error")
            return False

        if fingerimg == 1:
            print("Remove finger")
            time.sleep(1)
            while i != adafruit_fingerprint.NOFINGER:
                i = finger.get_image()

    print("Creating model...", end="")
    i = finger.create_model()
    if i == adafruit_fingerprint.OK:
        print("Created")
    else:
        if i == adafruit_fingerprint.ENROLLMISMATCH:
            print("Prints did not match")
        else:
            print("Other error")
        return False

    # Correctly format the print statement for storing the model
    print("Storing model #%d..." % fingerprint_id_int, end="")
    i = finger.store_model(fingerprint_id_int)  # Use integer for storing model
    if i == adafruit_fingerprint.OK:
        print("Stored")
    else:
        if i == adafruit_fingerprint.BADLOCATION:
            print("Bad storage location")
        elif i == adafruit_fingerprint.FLASHERR:
            print("Flash storage error")
        else:
            print("Other error")
        return False

    # Post it
    post_fingerprint(email, fingerprint_id_int)

    return True

def on_enroll_button_click():
    """Callback function for the enroll button."""
    selected_item = tree.selection()
    if not selected_item:
        messagebox.showwarning("Selection Error", "Please select a row from the table.")
        return

    item = tree.item(selected_item)
    email = item['values'][1]  # Assuming email is in the second column
    fingerprint_id = fingerprint_id_entry.get().strip()  # Get fingerprint_id from the entry widget

    if not fingerprint_id:
        messagebox.showwarning("Input Error", "Please enter a faculty ID.")
        return

    # Enroll fingerprint
    success = enroll_fingerprint(email, fingerprint_id)
    if not success:
        messagebox.showwarning("Enrollment Error", "Failed to enroll fingerprint.")

def refresh_table():
    """Refresh the table with data from the Laravel API."""
    for row in tree.get_children():
        tree.delete(row)

    faculty_data = fetch_faculty_data()
    for faculty in faculty_data:
        # Replace 'name' and 'email' with actual key names from the API response
        tree.insert("", tk.END, values=(faculty['name'], faculty['email']))

# Initialize Tkinter window

def center_window(window, width, height):
    # Get the screen width and height
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    # Calculate the x and y coordinates for the window to be centered
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)

    # Set the window geometry
    window.geometry(f'{width}x{height}+{x}+{y}')


root = tk.Tk()
root.configure(bg='#135D66')

root.title("Faculty Fingerprint Enrollment")

panel = tk.Frame(root, bg='#77B0AA')
panel.place(x=50, y=50, width=600, height=400)

# Create Treeview for displaying faculty data
columns = ("name", "email")
tree = ttk.Treeview(root, columns=columns, show="headings")

# Configure column widths
tree.column("name", width=250)  # Set width for "name" column
tree.column("email", width=250)  # Set width for "email" column

# Set headings
tree.heading("name", text="Name")
tree.heading("email", text="Email")

# Set height (number of visible rows)
tree.configure(height=10)  # Number of visible rows
tree.place(x=100, y=80)

bold_font = font.Font(size=10, weight="bold")

# Add Entry widget for manual fingerprint_id input
tk.Label(root, text="Faculty ID:", font=bold_font).place(x=150, y=329)
fingerprint_id_entry = tk.Entry(root)
fingerprint_id_entry.place(x=250, y=330)

# Refresh Button
refresh_button = tk.Button(root, text="Refresh Data", font=bold_font, width=20, height=2, command=refresh_table)
refresh_button.place(x=150, y=380)

# Enroll Button
enroll_button = tk.Button(root, text="Enroll Fingerprint", font=bold_font, width=20, height=2, command=on_enroll_button_click)
enroll_button.place(x=400, y=380)

# Load initial data
refresh_table()

center_window(root, 700, 500)

# Run the Tkinter event loop
root.mainloop()
