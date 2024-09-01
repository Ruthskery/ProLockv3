import tkinter as tk
from tkinter import messagebox, ttk, font
import requests
import time
import serial
import adafruit_fingerprint

# Laravel API endpoint URLs
api_url = "https://prolocklogger.pro/api/getuserbyfingerprint/"
API_URL = 'https://prolocklogger.pro/api'
FACULTIES_URL = f'{API_URL}/users/role/2'
ENROLL_URL = f'{API_URL}/users/update-fingerprint'

# Initialize serial connection for the fingerprint sensor
uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

def get_user(fingerprint_id):
    try:
        response = requests.get(f"{api_url}{fingerprint_id}")
        if response.status_code == 200:
            data = response.json()
            if 'name' in data:
                return data['name']
        return None
    except requests.RequestException as e:
        messagebox.showerror("Request Error", f"Failed to connect to API: {e}")
        return None

def fetch_faculty_data():
    """Fetch faculty data from the Laravel API, excluding those with exactly two or more registered fingerprint IDs."""
    try:
        response = requests.get(FACULTIES_URL)
        response.raise_for_status()
        data = response.json()

        # Filter out faculty members who have exactly two or more fingerprints registered
        filtered_data = [
            faculty for faculty in data 
            if faculty.get('fingerprint_id') is None or len(faculty.get('fingerprint_id', [])) < 2
        ]

        return filtered_data

    except requests.RequestException as e:
        messagebox.showerror("Error", f"Error fetching faculty data: {e}")
        return []



def post_fingerprint(email, fingerprint_id):
    """Post fingerprint data to the Laravel API."""
    try:
        url = f"{ENROLL_URL}?email={email}&fingerprint_id={fingerprint_id}"
        response = requests.put(url)
        response.raise_for_status()
        messagebox.showinfo("Success", "Fingerprint enrolled successfully")
    except requests.RequestException as e:
        messagebox.showerror("Error", f"User had already registered 2 fingerprints")

def enroll_fingerprint(email, fingerprint_id):
    """Enroll a fingerprint for a faculty member, ensuring it's not already registered twice."""
    print("Waiting for image...")
    while finger.get_image() != adafruit_fingerprint.OK:
        pass

    print("Templating...")
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        messagebox.showwarning("Error", "Failed to template the fingerprint image.")
        return False

    print("Searching for existing fingerprint...")
    if finger.finger_search() == adafruit_fingerprint.OK:
        existing_user = get_user(finger.finger_id)
        if existing_user:
            messagebox.showwarning("Error", f"Fingerprint already registered to {existing_user}")
            return False
        else:
            messagebox.showwarning("Error", "Fingerprint is already in use.")
            return False

    # Proceed to enrollment since fingerprint is not registered
    print("Place the same finger again...")
    while finger.get_image() != adafruit_fingerprint.OK:
        pass

    print("Templating second image...")
    if finger.image_2_tz(2) != adafruit_fingerprint.OK:
        messagebox.showwarning("Error", "Failed to template the second fingerprint image.")
        return False

    print("Creating model...")
    if finger.create_model() != adafruit_fingerprint.OK:
        messagebox.showwarning("Error", "Failed to create fingerprint model.")
        return False

    # Convert fingerprint_id to integer for storing
    try:
        fingerprint_id_int = int(fingerprint_id)
    except ValueError:
        messagebox.showwarning("Error", "Invalid fingerprint ID; it must be a number.")
        return False

    print(f"Storing model at location #{fingerprint_id_int}...")
    if finger.store_model(fingerprint_id_int) != adafruit_fingerprint.OK:
        messagebox.showwarning("Error", "Failed to store fingerprint model.")
        return False

    # Post the fingerprint data to the API
    post_fingerprint(email, fingerprint_id_int)
    return True


def on_enroll_button_click():
    """Callback function for the enroll button."""
    selected_item = tree.selection()
    if not selected_item:
        messagebox.showwarning("Selection Error", "Please select a row from the table.")
        return

    item = tree.item(selected_item)
    table_name = item['values'][0]  # Assuming name is in the first column
    email = item['values'][1]  # Assuming email is in the second column

    entered_name = faculty_name_entry.get().strip()  # Get the name from the entry widget
    fingerprint_id = fingerprint_id_entry.get().strip()  # Get fingerprint_id from the entry widget

    if not entered_name:
        messagebox.showwarning("Input Error", "Please enter a faculty name.")
        return

    if entered_name != table_name:
        messagebox.showwarning("Name Mismatch", "Entered name does not match the selected faculty name.")
        return

    if not fingerprint_id:
        messagebox.showwarning("Input Error", "Please enter a faculty ID.")
        return

    # Enroll fingerprint with provided email and fingerprint_id
    success = enroll_fingerprint(email, fingerprint_id)
    if not success:
        messagebox.showwarning("Enrollment Error", "Failed to enroll fingerprint.")

def refresh_table():
    """Refresh the table with data from the Laravel API."""
    # Clear the current rows in the table
    for row in tree.get_children():
        tree.delete(row)

    # Fetch and filter faculty data
    faculty_data = fetch_faculty_data()

    # Insert filtered data into the table
    for faculty in faculty_data:
        tree.insert("", tk.END, values=(faculty['name'], faculty['email']))


# Ensure to refresh the table to update the data after enrollment


# Initialize Tkinter window
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
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

# Add Entry widget for manual faculty name input
tk.Label(root, text="Faculty Name:", font=bold_font).place(x=150, y=299)
faculty_name_entry = tk.Entry(root)
faculty_name_entry.place(x=250, y=300)

# Add Entry widget for manual fingerprint_id input
tk.Label(root, text="Faculty ID:", font=bold_font).place(x=150, y=329)
fingerprint_id_entry = tk.Entry(root)
fingerprint_id_entry.place(x=250, y=330)

# Refresh Button
refresh_button = tk.Button(root, text="Refresh Data", font=bold_font, width=20, height=2, command=refresh_table)
refresh_button.place(x=150, y=380)

# Enroll Button
enroll_button = tk.Button(root, text="Enroll Fingerprint", font=bold_font, width=20, height=2,
                          command=on_enroll_button_click)
enroll_button.place(x=400, y=380)

# Load initial data
refresh_table()

center_window(root, 700, 500)

# Run the Tkinter event loop
root.mainloop()



