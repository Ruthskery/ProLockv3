import threading
import time
import serial
import adafruit_fingerprint
import nfc
import tkinter as tk
from tkinter import ttk, font, messagebox
from PIL import Image, ImageTk
import RPi.GPIO as GPIO
import requests
from datetime import datetime, timedelta
import pyttsx3  # Import pyttsx3 for text-to-speech
import pygame

API_URL = 'https://prolocklogger.pro/api'

# API URLs for Fingerprint, NFC, and Current Date-Time
FINGERPRINT_API_URL = f'{API_URL}/getuserbyfingerprint/'
TIME_IN_FINGERPRINT_URL = f'{API_URL}/logs/time-in/fingerprint'
TIME_OUT_FINGERPRINT_URL = f'{API_URL}/logs/time-out/fingerprint'
RECENT_LOGS_FINGERPRINT_URL2 = f'{API_URL}/recent-logs/by-fingerid'
LAB_SCHEDULE_FINGERPRINT_URL = f'{API_URL}/lab-schedules/fingerprint/'

USER_INFO_URL = f'{API_URL}/user-information/by-id-card'
RECENT_LOGS_URL = f'{API_URL}/recent-logs'
TIME_IN_URL = f'{API_URL}/logs/time-in'
TIME_OUT_URL = f'{API_URL}/logs/time-out'
RECENT_LOGS_URL2 = f'{API_URL}/recent-logs/by-uid'
CURRENT_DATE_TIME_URL = f'{API_URL}/current-date-time'
LAB_SCHEDULE_URL = f'{API_URL}/student/lab-schedule/rfid/'
LOGS_URL = f'{API_URL}/logs'

# Laravel API endpoint URLs
FACULTIES_URL = f'{API_URL}/users/role/2'
ENROLL_URL = f'{API_URL}/users/update-fingerprint'
ADMIN_URL = f'{API_URL}/admin/role/1'

# GPIO pin configuration for the solenoid lock and buzzer
SOLENOID_PIN = 17
BUZZER_PIN = 27

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(SOLENOID_PIN, GPIO.OUT)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

# Initialize serial connection for the fingerprint sensor
uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)


# Initialize Tkinter window
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')

# Initialize pygame mixer for audio playback
pygame.mixer.init()

class FingerprintEnrollment:

    def __init__(self, root, attendance_app):
        self.root = root
        self.attendance_app = attendance_app
        self.frame = ttk.Frame(root)
        self.next_fingerprint_id = self.get_highest_fingerprint_id() + 1  # Properly initialize next_fingerprint_id

        # Create a canvas to handle the background color as ttk.Frame does not directly support bg color
        self.canvas = tk.Canvas(self.frame, bg='#2D3F7C')
        self.canvas.pack(fill="both", expand=True)

        # Centering the panel within the canvas
        panel = tk.Frame(self.canvas, bg='#F6F5FB')
        panel.place(relx=0.5, rely=0.5, anchor='center', width=1100, height=700)  # Adjust height as needed

        # Create the heading frame to organize images and heading text
        heading_frame = ttk.Frame(panel, padding="10", style="ContainerFrame.TFrame")
        heading_frame.pack(fill="x")

        # Load and place the left image as a button with command to open fingerprint enrollment
        left_image_path = "prolockk.png"  # Replace with your left image file path
        left_image = Image.open(left_image_path).resize((170, 50))
        left_photo = ImageTk.PhotoImage(left_image)
        left_image_button = tk.Button(
            heading_frame,
            image=left_photo,
            bg="#F6F5FB",
            borderwidth=0,  # Remove border for a clean look
            command=self.back_to_attendance
        )
        left_image_button.image = left_photo  # Keep a reference to avoid garbage collection
        left_image_button.pack(side="left", padx=1)

        # Define custom fonts
        heading_font = font.Font(family="Exo 2", size=16, weight="bold")

        # Create the main heading and center it
        main_heading = tk.Label(panel, text="Faculty Fingerprint Registration",
                                font=("Exo 2", 20, "bold"), fg="#000000", bg="#F6F5FB")
        main_heading.place(relx=0.5, rely=0.07, anchor="center")

        # Load and place the first right image (40x40)
        right_image1_path = "cspclogo.png"  # Replace with your first right image file path
        right_image1 = Image.open(right_image1_path).resize((60, 60))
        right_photo1 = ImageTk.PhotoImage(right_image1)
        right_image_label1 = tk.Label(heading_frame, image=right_photo1, bg="#F6F5FB")
        right_image_label1.image = right_photo1  # Keep a reference to avoid garbage collection
        right_image_label1.pack(side="right", padx=5)

        # Load and place the second right image (40x40)
        right_image2_path = "ccslogo.png"  # Replace with your second right image file path
        right_image2 = Image.open(right_image2_path).resize((60, 60))
        right_photo2 = ImageTk.PhotoImage(right_image2)
        right_image_label2 = tk.Label(heading_frame, image=right_photo2, bg="#F6F5FB")
        right_image_label2.image = right_photo2  # Keep a reference to avoid garbage collection
        right_image_label2.pack(side="right", padx=5)

        # Style configuration for the Treeview
        style = ttk.Style()
        style.configure("LogsTable.Treeview.Heading", background="#D3D1ED", font=("Helvetica", 10, "bold"))
        style.configure("LogsTable.Treeview", background="#F6F5FB", fieldbackground="#F6F5FB", rowheight=25)
        style.configure("ContainerFrame.TFrame", background="#F6F5FB")
        style.configure("Vertical.TScrollbar", background="#D3D1ED", troughcolor="#D3D1ED", bordercolor="#D3D1ED",
                        arrowcolor="#000000")

        # Treeview for displaying faculty and admin data with Name and Email columns only
        columns = ("name", "email")
        self.tree = ttk.Treeview(panel, columns=columns, show="headings", style="LogsTable.Treeview")
        self.tree.place(relx=1, rely=1)

        # Configure Treeview column widths and headings
        self.tree.column("name", width=350)  # Set width for "name" column
        self.tree.column("email", width=350)  # Set width for "email" column
        self.tree.heading("name", text="Name")
        self.tree.heading("email", text="Email")
        self.tree.configure(height=10)  # Number of visible rows

        # Create a vertical scrollbar and link it to the Treeview
        self.scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        # Place the Treeview and scrollbar within the panel
        self.tree.place(relx=0.5, rely=0.4, anchor='center')
        self.scrollbar.place(relx=0.83, rely=0.4, anchor='center',
                             relheight=0.38)  # Adjust relheight to match the Treeview height

        # Font setup for buttons
        bold_font = font.Font(family="Exo 2", size=10, weight="bold")

        # Center the buttons below the Treeview in the panel
        button_y_start = 0.70  # Relative y position for buttons (70% from top of the panel)
        button_spacing = 0.10  # Relative spacing between buttons

        # Refresh Button
        refresh_button = tk.Button(panel, text="Refresh Data", font=bold_font, width=20, height=2, bg="#D3D1ED",
                                   command=self.refresh_table)
        refresh_button.place(relx=0.39, rely=button_y_start, anchor='center')

        # Enroll Button
        enroll_button = tk.Button(panel, text="Enroll Fingerprint", font=bold_font, width=20, height=2, bg="#D3D1ED",
                                  command=self.on_enroll_button_click)
        enroll_button.place(relx=0.61, rely=button_y_start, anchor='center')

        # Error Message Label (Added below the buttons)
        self.message_label = tk.Label(panel, text="", font=("Exo 2", 16), fg="red", bg="#F6F5FB")
        self.message_label.place(relx=0.5, rely=button_y_start + button_spacing, anchor='center')

        # Load initial data
        self.refresh_table()

    def show(self):
        """Show the Fingerprint Enrollment frame."""
        self.frame.pack(fill="both", expand=True)

    def hide(self):
        """Hide the Fingerprint Enrollment frame."""
        self.frame.pack_forget()

    def back_to_attendance(self):
        """Hide current frame and show AttendanceApp frame."""
        self.hide()
        self.attendance_app.show()
        self.attendance_app.start_fingerprint_scanning()  # Restart fingerprint scanning

    def get_user(self, fingerprint_id):
        """Fetch user information by fingerprint ID."""
        try:
            response = requests.get(f"{FINGERPRINT_API_URL}{fingerprint_id}")
            response.raise_for_status()
            data = response.json()
            if 'name' in data:
                return data['name']
            return None
        except requests.RequestException as e:
            messagebox.showerror("Request Error", f"Failed to connect to API: {e}")
            return None

    def fetch_faculty_data(self):
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

    def fetch_admin_data(self):
        """Fetch admin data from the Laravel API, excluding those with exactly two or more registered fingerprint IDs."""
        try:
            response = requests.get(ADMIN_URL)
            response.raise_for_status()
            data = response.json()

            # Filter out admin members who have exactly two or more fingerprints registered
            filtered_data = [
                admin for admin in data
                if admin.get('fingerprint_id') is None or len(admin.get('fingerprint_id', [])) < 2
            ]

            return filtered_data

        except requests.RequestException as e:
            messagebox.showerror("Error", f"Error fetching faculty data: {e}")
            return []

    def post_fingerprint(self, email, fingerprint_id):
        """Post fingerprint data to the Laravel API."""
        try:
            url = f"{ENROLL_URL}?email={email}&fingerprint_id={fingerprint_id}"
            response = requests.put(url)
            response.raise_for_status()
            # messagebox.showinfo("Success", "Fingerprint enrolled successfully")
            self.update_message(f"Fingerprint enrolled successfully", color="green")
        except requests.RequestException as e:
            # messagebox.showerror("Error", f"Error posting fingerprint data: {e}")
            self.update_message(f"Error posting fingerprint data: {e}", color="red")


    def get_highest_fingerprint_id(self):
        """Fetch the highest fingerprint ID stored in the sensor."""
        try:
            # Read all stored fingerprint templates
            if finger.read_templates() != adafruit_fingerprint.OK:
                return 0  # Return 0 if no fingerprints are stored

            # Find the highest ID among the stored fingerprints
            if finger.templates:
                return max(finger.templates)
            else:
                return 0
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read stored fingerprints: {e}")
            return 0

    def check_fingerprint_exists(self):
        """Check if the current fingerprint is already registered."""
        print("Searching for existing fingerprint...")
        if finger.finger_search() == adafruit_fingerprint.OK:
            existing_user = self.get_user(finger.finger_id)
            if existing_user:
                # messagebox.showwarning("Error", f"Fingerprint already registered to {existing_user}")
                self.update_message(f"Fingerprint already registered to {existing_user}", color="red")
                return True
        return False

    def enroll_fingerprint(self, email):
        """Enroll a fingerprint for a faculty member, ensuring it's not already registered."""
        print("Waiting for image...")
        self.update_message(f"Waiting for image...", color="green")
        # Attempt to capture the first image
        while finger.get_image() != adafruit_fingerprint.OK:
            pass

        print("Templating first image...")
        if finger.image_2_tz(1) != adafruit_fingerprint.OK:
            # messagebox.showwarning("Error", "Failed to template the first fingerprint image.")
            self.update_message(f"Failed to template the first fingerprint image.", color="red")
            return False

        print("Checking if fingerprint is already registered...")
        if finger.finger_search() == adafruit_fingerprint.OK:
            existing_user = self.get_user(finger.finger_id)
            if existing_user:
                # messagebox.showwarning("Error", f"Fingerprint already registered to {existing_user}")
                self.update_message(f"Fingerprint already registered to {existing_user}", color="red")
                return False

        # Prompt to place the finger again for verification
        print("Place the same finger again...")
        time.sleep(3)
        while finger.get_image() != adafruit_fingerprint.OK:
            pass

        print("Templating second image...")
        if finger.image_2_tz(2) != adafruit_fingerprint.OK:
            # messagebox.showwarning("Error", "Failed to template the second fingerprint image.")
            self.update_message(f"Failed to template the second fingerprint image.", color="red")
            return False

        print("Re-Checking if fingerprint is already registered...")
        if finger.finger_search() == adafruit_fingerprint.OK:
            existing_user = self.get_user(finger.finger_id)
            if existing_user:
                # messagebox.showwarning("Error", f"Fingerprint already registered to {existing_user}")
                self.update_message(f"Fingerprint already registered to {existing_user}", color="red")
                return False

        print("Creating model from images...")
        if finger.create_model() != adafruit_fingerprint.OK:
            # messagebox.showwarning("Error", "Failed to create fingerprint model from images.")
            self.update_message(f"Failed to create fingerprint model from images.", color="red")

            return False

        # Use self.next_fingerprint_id here
        print(f"Storing model at location #{self.next_fingerprint_id}...")
        if finger.store_model(self.next_fingerprint_id) != adafruit_fingerprint.OK:
            # messagebox.showwarning("Error", "Failed to store fingerprint model.")
            self.update_message(f"Failed to store fingerprint model.", color="red")
            return False

        # Post the fingerprint data to the API
        self.post_fingerprint(email, self.next_fingerprint_id)
        self.next_fingerprint_id += 1  # Increment the ID for the next registration
        return True

    def on_enroll_button_click(self):
        """Callback function for the enroll button."""
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a row from the table.")
            return

        item = self.tree.item(selected_item)
        table_name = item['values'][0]  # Assuming name is in the first column
        email = item['values'][1]  # Assuming email is in the second column

        # Enroll fingerprint with the selected email
        success = self.enroll_fingerprint(email)
        if not success:
            print("Enrollment Error", "Failed to enroll fingerprint.")
        else:
            # Refresh the table to update or remove the faculty if they now have 2 fingerprints
            self.refresh_table()

    def refresh_table(self):
        """Refresh the table with data from the Laravel API."""
        for row in self.tree.get_children():
            self.tree.delete(row)

        faculty_data = self.fetch_faculty_data()
        for faculty in faculty_data:
            # Only display faculty who have less than 2 fingerprints registered
            self.tree.insert("", tk.END, values=(faculty['name'], faculty['email']))

        admin_data = self.fetch_admin_data()
        for admin in admin_data:
            # Only display admin who have less than 2 fingerprints registered
            self.tree.insert("", tk.END, values=(admin['name'], admin['email']))

    def update_message(self, message, color="red"):
        """Update the message label with the provided message and color."""
        self.message_label.config(text=message, fg=color)
        self.root.update_idletasks()  # Force GUI update to display the message immediately
        self.root.after(5000, self.clear_message)  # Clears the message after 5 seconds

    def clear_message(self):
        """Clear the message label."""
        self.message_label.config(text="")

class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fingerprint and NFC Reader")
        self.root.attributes("-fullscreen", True)  # Set the window to full screen

        # Add key binding to exit full screen
        self.root.bind("<Escape>", self.exit_full_screen)

        # Initialize the text-to-speech engine
        try:
            self.speech_engine = pyttsx3.init(driverName='espeak')  # Ensure the correct driver is used for Raspberry Pi
            self.speech_engine.setProperty('rate', 150)  # Set speech rate
            self.speech_engine.setProperty('volume', 0.9)  # Set volume level
        except Exception as e:
            print(f"Failed to initialize TTS engine: {e}")
            self.speech_engine = None  # Set to None to handle in speak method

        # Initialize the last scan time
        self.last_scan_time = None  # Initialize last_scan_time to None

        # Define custom fonts
        heading_font = font.Font(family="Exo 2", size=16, weight="bold")
        label_font = font.Font(family="Exo 2", size=20, weight="bold")

        # Create a style for the main frame with a black background
        style = ttk.Style()
        style.configure("MainFrame.TFrame", background="#2D3F7C")
        style.configure("ContainerFrame.TFrame", background="#F6F5FB")  # Style for NFC and Fingerprint container frames

        # Create the main frame with specified dimensions
        self.main_frame = ttk.Frame(self.root, padding="20", width=1400, height=800, style="MainFrame.TFrame")
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.pack_propagate(False)  # Prevent the frame from resizing to fit its contents

        # Create the heading frame to organize images and heading text
        heading_frame = ttk.Frame(self.main_frame, padding="10", style="ContainerFrame.TFrame")
        heading_frame.pack(fill="x")

        # Load and place the left image as a button with command to open fingerprint enrollment
        left_image_path = "prolockk.png"  # Replace with your left image file path
        left_image = Image.open(left_image_path).resize((170, 50))
        left_photo = ImageTk.PhotoImage(left_image)
        left_image_button = tk.Button(
            heading_frame,
            image=left_photo,
            bg="#F6F5FB",
            borderwidth=0,  # Remove border for a clean look
            command=self.open_fingerprint_enrollment
        )
        left_image_button.image = left_photo  # Keep a reference to avoid garbage collection
        left_image_button.pack(side="left", padx=1)

        # Create a separate frame for the main heading to center it
        center_frame = ttk.Frame(heading_frame, style="ContainerFrame.TFrame")
        center_frame.pack(side="left", fill="x", expand=True)

        # Real-time clock label placed above the main heading
        self.clock_label = tk.Label(center_frame, font=("Exo 2", 30), fg="red", bg="#F6F5FB")
        self.clock_label.pack(anchor="center", pady=(0, 10))  # Center the clock label with some padding

        # Start the clock update
        self.update_clock()

        # Create the main heading and center it
        main_heading = tk.Label(center_frame, text="Fingerprint and RFID Attendance System",
                                font=("Exo 2", 20, "bold"), fg="#000000", bg="#F6F5FB")
        main_heading.pack(anchor="center")  # Center the label in the frame

        # Load and place the first right image (40x40)
        right_image1_path = "cspclogo.png"  # Replace with your first right image file path
        right_image1 = Image.open(right_image1_path).resize((60, 60))
        right_photo1 = ImageTk.PhotoImage(right_image1)
        right_image_label1 = tk.Label(heading_frame, image=right_photo1, bg="#F6F5FB")
        right_image_label1.image = right_photo1  # Keep a reference to avoid garbage collection
        right_image_label1.pack(side="right", padx=5)

        # Load and place the second right image (40x40)
        right_image2_path = "ccslogo.png"  # Replace with your second right image file path
        right_image2 = Image.open(right_image2_path).resize((60, 60))
        right_photo2 = ImageTk.PhotoImage(right_image2)
        right_image_label2 = tk.Label(heading_frame, image=right_photo2, bg="#F6F5FB")
        right_image_label2.image = right_photo2  # Keep a reference to avoid garbage collection
        right_image_label2.pack(side="right", padx=5)

        # Top frame for fingerprint and NFC
        top_frame = ttk.Frame(self.main_frame, padding="10", style="ContainerFrame.TFrame")  # Use self.main_frame
        top_frame.pack(side="top", fill="x")

        # Fingerprint frame
        left_frame = ttk.Frame(top_frame, padding="10", style="ContainerFrame.TFrame")
        left_frame.pack(side="left", fill="y", expand=True)
        fingerprint_label = ttk.Label(left_frame, text="Fingerprint Sensor", font=("Exo 2", 18, "bold"), background="#F6F5FB")
        fingerprint_label.pack(pady=20)

        # Load and resize an image
        image_path = "fingericon.png"  # Replace with your image file path
        desired_width = 150
        desired_height = 130

        # Load and resize the image
        image = Image.open(image_path)
        image = image.resize((desired_width, desired_height))
        photo = ImageTk.PhotoImage(image)

        # Create and pack the image label
        image_label = tk.Label(left_frame, image=photo, bg="#F6F5FB")
        image_label.image = photo  # Keep a reference to the image
        image_label.pack()  # Pack the image label to make it appear

        # NFC frame
        right_frame = ttk.Frame(top_frame, padding="10", style="ContainerFrame.TFrame")
        right_frame.pack(side="right", fill="y", expand=True)

        # Student Number, Name, Year, Section labels and entries
        self.student_number_entry = self.create_label_entry(right_frame, "Student Number:", label_font)
        self.name_entry = self.create_label_entry(right_frame, "Name:", label_font)
        self.year_entry = self.create_label_entry(right_frame, "Year:", label_font)
        self.section_entry = self.create_label_entry(right_frame, "Section:", label_font)

        # Error Message Label
        self.error_label = tk.Label(self.main_frame, text="", font=("Exo 2", 20, "bold", "italic"), foreground="green", bg="#2D3F7C")
        # Use self.main_frame
        self.error_label.pack(pady=10)

        # Logs Table
        self.create_logs_table()  # Ensure you use self.create_logs_table()

        # Fetch and display recent logs
        self.fetch_recent_logs()

        # Button to go to Fingerprint Enrollment
        # enrollment_button = tk.Button(self.main_frame, text="Go to Fingerprint Enrollment", command=self.open_fingerprint_enrollment)  # Use self.main_frame
        # enrollment_button.pack(pady=20)

        # Initialize NFC reader
        try:
            self.clf = nfc.ContactlessFrontend('usb')
        except Exception as e:
            print("NFC Error", f"Failed to initialize NFC reader: {e}")
            self.clf = None

        self.running = True
        self.nfc_thread = threading.Thread(target=self.read_nfc_loop)
        self.nfc_thread.start()

        # Initialize serial connection for fingerprint sensor
        self.finger = self.initialize_serial()

        # Start fingerprint scanning in a separate thread
        self.fingerprint_thread = threading.Thread(target=self.auto_scan_fingerprint)
        self.fingerprint_thread.start()

        # Track the last time-in for each user by fingerprint ID
        self.last_time_in = {}
        self.is_manual_unlock = False  # Flag to check if the door was manually unlocked

        # Start periodic checking of log status
        self.root.after(1000, self.check_log_status_periodically)  # Check log status every 10 seconds

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_clock(self):
        """Update the clock label with the current time from the API."""
        # Fetch the current date and time from the API
        current_time_data = self.fetch_current_date_time()

        if current_time_data:
            # Construct the time string based on the API response
            day_of_week = current_time_data.get('day_of_week', 'Unknown Day')
            date = current_time_data.get('date', 'Unknown Date')
            month = current_time_data.get('month', 'Unknown Month')
            year = current_time_data.get('year', 'Unknown Year')
            current_time = current_time_data.get('current_time', 'Unknown Time')

            # Format the time string
            formatted_time = f"{day_of_week} {month}-{date}-{year} {current_time}"

            # Update the clock label with the fetched time
            self.clock_label.config(text=formatted_time)
        else:
            # Fallback to display if API fails
            self.clock_label.config(text="Failed to fetch time from API")

        # Schedule the next update after 1 second
        self.root.after(1000, self.update_clock)

    def exit_full_screen(self, event=None):
        """Exit full screen mode."""
        self.root.attributes("-fullscreen", False)

    def show(self):
        self.main_frame.pack(fill="both", expand=True)

    def hide(self):
        self.main_frame.pack_forget()

    def open_fingerprint_enrollment(self):
        self.stop_fingerprint_scanning()  # Stop fingerprint scanning thread to prevent conflicts
        self.hide()  # Hide the current frame
        self.fingerprint_enrollment = FingerprintEnrollment(self.root, self)
        self.fingerprint_enrollment.show()  # Show the FingerprintEnrollment frame

    def create_label_entry(self, frame, text, font_style):
        label = ttk.Label(frame, text=text, font=font_style, background="#F6F5FB")
        label.pack(pady=5)
        entry = ttk.Entry(frame, font=font_style)
        entry.pack(pady=5)
        return entry

    def create_logs_table(self):
        # Create a new style for the Treeview with background color set to #D3D1ED
        style = ttk.Style()
        style.configure("LogsTable.Treeview.Heading", background="#D3D1ED", font=("Exo 2", 10, "bold"))
        style.configure("LogsTable.Treeview", background="#F6F5FB", fieldbackground="#F6F5FB", rowheight=25)
        style.map("LogsTable.Treeview",
                  background=[('selected', '#B0B0E0')])  # Optional: set a different color for selected rows
        table_frame = ttk.Frame(self.main_frame, padding="10", style="ContainerFrame.TFrame")
        table_frame.pack(side="bottom", fill="both", expand=True)
        columns = ("Date", "Name", "PC", "Student Number", "Year", "Section","Instructor", "Time-in", "Time-out")
        self.logs_tree = ttk.Treeview(table_frame, columns=columns, show='headings', style="LogsTable.Treeview")
        self.logs_tree.pack(pady=10, fill='both', expand=True)
        for col in columns:
            self.logs_tree.heading(col, text=col)
            self.logs_tree.column(col, minwidth=100, width=100, anchor='center')

    def initialize_serial(self):
        try:
            uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)
            return adafruit_fingerprint.Adafruit_Fingerprint(uart)
        except serial.SerialException as e:
            print("Serial Error", f"Failed to connect to serial port: {e}")
            return None

    def unlock_door(self):
        GPIO.output(SOLENOID_PIN, GPIO.LOW)
        print("Door unlocked.")

    def lock_door(self):
        GPIO.output(SOLENOID_PIN, GPIO.HIGH)
        print("Door locked.")

    def speak(self, message):
        """Utility method to handle text-to-speech."""
        if self.speech_engine:
            self.speech_engine.say(message)
            self.speech_engine.runAndWait()

    def fetch_latest_log_status(self):
        try:
            # Fetch the latest logs from the server
            response = requests.get(LOGS_URL)
            response.raise_for_status()
            logs = response.json().get("logs", [])

            if logs:
                latest_log = logs[-1]  # Get the latest log (assuming logs are in chronological order)
                status = latest_log.get("status", "")
                action_type = latest_log.get("action_type", "")

                # Handle remote actions (manual unlock or lock)
                if action_type == "manual_unlock":
                    if self.is_door_locked():  # Only unlock if it's currently locked
                        self.unlock_door()
                        print("Door unlocked by remote action.")
                elif action_type == "manual_lock":
                    if not self.is_door_locked():  # Only lock if it's currently unlocked
                        self.lock_door()
                        print("Door locked by remote action.")

                # Handle automatic lock/unlock based on the status field
                if status == "close" and not self.is_door_locked():  # Check if the door needs to be locked
                    self.lock_door()
                    print("Door locked automatically based on log status.")
                    self.update_door_status(self.finger.finger_id, 'close')  # Update the door status to 'close'

                elif status == "open" and self.is_door_locked():  # Check if the door needs to be unlocked
                    self.unlock_door()
                    print("Door unlocked automatically based on log status.")
                    self.update_door_status(self.finger.finger_id, 'open')  # Update the door status to 'open'

        except requests.RequestException as e:
            print(f"Error fetching log status: {e}")

    def is_door_locked(self):
        # Function to check the current state of the door (you can track it via a GPIO pin)
        return GPIO.input(SOLENOID_PIN) == GPIO.HIGH

    def check_log_status_periodically(self):
        self.fetch_latest_log_status()
        self.root.after(10000, self.check_log_status_periodically)  # Call again after 10 seconds

    def get_user_details(self, fingerprint_id):
        try:
            response = requests.get(f"{FINGERPRINT_API_URL}{fingerprint_id}")
            response.raise_for_status()
            data = response.json()
            return data.get('name', None)
        except requests.RequestException as e:
            print("API Error", f"Failed to fetch data from API: {e}")
            return None

    def fetch_current_date_time(self):
        try:
            response = requests.get(CURRENT_DATE_TIME_URL)
            response.raise_for_status()
            data = response.json()
            if 'day_of_week' in data and 'current_time' in data:
                return data
            else:
                print("Error: Missing expected keys in the API response.")
                return None
        except requests.RequestException as e:
            print(f"Error fetching current date and time from API: {e}")
            return None

    def update_current_date_time(self):
        """Fetch and update the current date and time in the label."""
        current_time_data = self.fetch_current_date_time()
        if current_time_data:
            current_day = current_time_data.get('day_of_week', 'Unknown Day')
            current_time = current_time_data.get('current_time', 'Unknown Time')
            self.date_time_label.config(text=f"{current_day}, {current_time}")
        else:
            self.date_time_label.config(text="Failed to fetch current date and time")

        # Update the current date and time every minute
        self.root.after(60000, self.update_current_date_time)

    def get_schedule(self, fingerprint_id):
        try:
            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                print("Error: Could not fetch current date and time from API.")
                return False

            current_day = current_time_data.get('day_of_week')  # Example: "Wednesday"
            current_time = current_time_data.get('current_time')  # Example: "06:30"
            current_date = datetime.now().date()  # Fetch today's date

            # Convert the current time to a time object for comparison
            current_time_obj = datetime.strptime(current_time, "%H:%M").time()

            if not current_day or not current_time:
                print("Error: Invalid response from current date-time API.")
                return False

            print(f"Current Day from API: {current_day}, Current Time from API: {current_time}")

            response = requests.get(f"{LAB_SCHEDULE_FINGERPRINT_URL}{fingerprint_id}")
            response.raise_for_status()
            schedules = response.json()

            for schedule in schedules:
                schedule_day = schedule.get('day_of_the_week')
                start_time = schedule.get('class_start')
                end_time = schedule.get('class_end')
                is_makeup_class = schedule.get('is_makeup_class', 0)
                specific_date = schedule.get('specific_date')

                if start_time and end_time:
                    # Convert start and end times to time objects
                    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
                    end_time_obj = datetime.strptime(end_time, "%H:%M").time()

                    # For regular classes, use `day_of_the_week`
                    if not is_makeup_class:
                        if schedule_day and schedule_day.lower() == current_day.lower():
                            if start_time_obj <= current_time_obj < end_time_obj:
                                print("Access allowed based on regular schedule.")
                                return True

                    # For makeup classes, use `specific_date`
                    elif is_makeup_class == 1:
                        if specific_date:
                            schedule_date = datetime.strptime(specific_date, '%Y-%m-%d').date()
                            if schedule_date == current_date:
                                if start_time_obj <= current_time_obj < end_time_obj:
                                    print("Access allowed based on makeup class schedule.")
                                    return True

            print("Access denied: No matching schedule found or not within allowed time.")
            return False

        except requests.RequestException as e:
            print(f"Request Error: Failed to connect to API: {e}")
            return False

    def get_schedule_mock_up(self, fingerprint_id):
        try:
            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                print("Error: Could not fetch current date and time from API.")
                return False

            current_day = current_time_data.get('day_of_week')
            current_time = current_time_data.get('current_time')
            current_date = datetime.now().date()  # Fetch current date

            if not current_day or not current_time:
                print("Error: Invalid response from current date-time API.")
                return False

            print(f"Current Day from API: {current_day}, Current Time from API: {current_time}")

            response = requests.get(f"{LAB_SCHEDULE_FINGERPRINT_URL}{fingerprint_id}")
            response.raise_for_status()
            schedules = response.json()

            for schedule in schedules:
                specific_date = schedule.get('specific_date')
                start_time = schedule.get('class_start')
                end_time = schedule.get('class_end')  # Assuming end time is available in the schedule data

                if specific_date and start_time and end_time:
                    # Convert specific_date string to a date object
                    schedule_date = datetime.strptime(specific_date, '%Y-%m-%d').date()

                    print(f"Checking Schedule: Date: {schedule_date}, Start: {start_time}, End: {end_time}")

                    # Check if the schedule date matches the current date
                    if schedule_date == current_date:
                        # Check if the current time is within the scheduled time period
                        if start_time <= current_time < end_time:
                            print("Access allowed based on schedule.")
                            return True

            print("Access denied: No matching schedule found or not within allowed time.")
            return False
        except requests.RequestException as e:
            print("Request Error", f"Failed to connect to API: {e}")
            return False

    def get_rfid_schedule(self, rfid_number):
        try:
            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                print("Error: Could not fetch current date and time from API.")
                return False

            current_day = current_time_data.get('day_of_week')
            current_time = current_time_data.get('current_time')

            if not current_day or not current_time:
                print("Error: Invalid response from current date-time API.")
                return False

            print(f"Current Day from API: {current_day}, Current Time: {current_time}")

            response = requests.get(f"{LAB_SCHEDULE_URL}{rfid_number}")
            response.raise_for_status()
            schedules = response.json()

            for schedule in schedules:
                schedule_day = schedule.get('day_of_the_week')
                start_time = schedule.get('class_start')
                end_time = schedule.get('class_end')  # Assuming class_end is available
                is_makeup_class = schedule.get('is_makeup_class', 0)
                specific_date = schedule.get('specific_date', 'N/A')

                if is_makeup_class == 0 and schedule_day and start_time and end_time:
                    print(f"Checking Regular Schedule: Day: {schedule_day}, Start: {start_time}, End: {end_time}")

                    # Check if the current day matches the schedule day
                    if schedule_day.lower() == current_day.lower():
                        # Check if the current time is within the scheduled class period
                        if start_time <= current_time < end_time:
                            print("Access allowed based on regular schedule.")
                            return True

            print("Access denied: No matching regular schedule found or not within allowed time.")
            return False
        except requests.RequestException as e:
            print(f"Error fetching or checking schedule: {e}")
            return False

    def get_rfid_schedule_mock_up(self, rfid_number):
        try:
            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                print("Error: Could not fetch current date and time from API.")
                return False

            current_time = current_time_data.get('current_time')
            current_date = datetime.now().date()  # Fetch current date

            if not current_time:
                print("Error: Invalid response from current date-time API.")
                return False

            print(f"Current Date: {current_date}, Current Time: {current_time}")

            response = requests.get(f"{LAB_SCHEDULE_URL}{rfid_number}")
            response.raise_for_status()
            schedules = response.json()

            for schedule in schedules:
                specific_date = schedule.get('specific_date')
                start_time = schedule.get('class_start')
                end_time = schedule.get('class_end')  # Assuming class_end is available
                is_makeup_class = schedule.get('is_makeup_class', 0)

                if is_makeup_class == 1 and specific_date and start_time and end_time:
                    # Convert specific_date string to a date object
                    if specific_date != 'N/A':
                        schedule_date = datetime.strptime(specific_date, '%Y-%m-%d').date()
                        print(f"Checking Make-Up Schedule: Date: {schedule_date}, Start: {start_time}, End: {end_time}")

                        # Check if the schedule date matches the current date
                        if schedule_date == current_date:
                            # Check if the current time is within the scheduled make-up class period
                            if start_time <= current_time < end_time:
                                print("Access allowed based on make-up schedule.")
                                return True

            print("Access denied: No matching make-up schedule found or not within allowed time.")
            return False
        except requests.RequestException as e:
            print(f"Error fetching or checking schedule: {e}")
            return False

    def check_if_makeup_class_rfid(self, rfid_number):
        """
        Check if the class associated with the given RFID number is a make-up class.
        Returns True if any class is a make-up class; otherwise, returns False.
        """
        try:
            response = requests.get(f"{LAB_SCHEDULE_URL}{rfid_number}")
            response.raise_for_status()
            schedules = response.json()

            for schedule in schedules:
                # Check if 'is_makeup_class' is 1, indicating a make-up class
                if schedule.get('is_makeup_class') == 1:
                    return True
            return False
        except requests.RequestException as e:
            print(f"Error checking if class is a make-up class: {e}")
            return False

    def check_time_in_record_fingerprint(self, fingerprint_id):
        try:
            url = f"{RECENT_LOGS_FINGERPRINT_URL2}?fingerprint_id={fingerprint_id}"
            response = requests.get(url)
            response.raise_for_status()
            logs = response.json()
            return any(log.get('time_in') and not log.get('time_out') for log in logs)
        except requests.RequestException as e:
            print(f"Error checking Time-In record: {e}")
            return False

    def record_time_in_fingerprint(self, fingerprint_id, user_name, role_id="2"):
        try:
            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                return
            url = f"{TIME_IN_FINGERPRINT_URL}?fingerprint_id={fingerprint_id}&time_in={current_time_data['current_time']}&user_name={user_name}&role_id={role_id}"
            response = requests.put(url)
            response.raise_for_status()
            print("Time-In recorded successfully.")
            print("Success", "Time-In recorded successfully.")
            print("Door unlocked!")
        except requests.RequestException as e:
            print("Error", f"Error recording Time-In: {e}")

    def record_time_out_fingerprint(self, fingerprint_id):
        try:
            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                return
            url = f"{TIME_OUT_FINGERPRINT_URL}?fingerprint_id={fingerprint_id}&time_out={current_time_data['current_time']}"
            response = requests.put(url)
            response.raise_for_status()
            print("Time-Out recorded successfully.")
            print("Door locked!")
        except requests.RequestException as e:
            print(f"Error recording Time-Out: {e}")

    def stop_fingerprint_scanning(self):
        """Stop the fingerprint scanning thread to avoid conflicts when enrolling fingerprints."""
        if self.finger:  # Check if the fingerprint scanner is initialized
            self.finger._uart.close()  # Close the serial connection to the fingerprint sensor

        self.running = False  # This flag is used to stop the scanning loop
        if self.fingerprint_thread.is_alive():
            self.fingerprint_thread.join()  # Ensure the thread has completely stopped
        print("Fingerprint scanning stopped.")

    def open_fingerprint_enrollment(self):
        self.stop_fingerprint_scanning()  # Stop fingerprint scanning thread and close the connection
        self.hide()  # Hide the current frame
        self.fingerprint_enrollment = FingerprintEnrollment(self.root, self)
        self.fingerprint_enrollment.show()  # Show the FingerprintEnrollment frame

    def stop_fingerprint_scanning(self):
        """Stop the fingerprint scanning thread to avoid conflicts when enrolling fingerprints."""
        self.running = False  # Stop the scanning loop
        if self.fingerprint_thread.is_alive():
            self.fingerprint_thread.join()  # Ensure the thread has stopped
        print("Fingerprint scanning stopped.")

    def start_fingerprint_scanning(self):
        self.finger = self.initialize_serial()  # Re-initialize the serial connection to the fingerprint scanner

        self.running = True  # Set the running flag to True
        self.fingerprint_thread = threading.Thread(target=self.auto_scan_fingerprint)
        self.fingerprint_thread.start()  # Start fingerprint scanning thread again
        print("Fingerprint scanning started.")

    def play_welcome_song(self):
        """Play the welcome.mp3 song for 2 seconds when the door is unlocked."""
        try:
            pygame.mixer.music.load("welcome.mp3")  # Load the MP3 file
            pygame.mixer.music.play()  # Start playing the song
            time.sleep(2)  # Wait for 2 seconds
            pygame.mixer.music.stop()  # Stop the song after 11 seconds
        except pygame.error as e:
            print(f"Failed to play tabi.mp3: {e}")

    def play_wrong_song(self):
        """Play the farewell.mp3 song for 15 seconds when the door is unlocked."""
        try:
            pygame.mixer.music.load("wrong.mp3")  # Load the MP3 file
            pygame.mixer.music.play()  # Start playing the song
            time.sleep(1)  # Wait for 11 seconds
            pygame.mixer.music.stop()  # Stop the song after 15 seconds
        except pygame.error as e:
            print(f"Failed to play farewell.mp3: {e}")

    def play_tot_sound(self):
        """Play the farewell.mp3 song for 15 seconds when the door is unlocked."""
        try:
            pygame.mixer.music.load("beep.mp3")  # Load the MP3 file
            pygame.mixer.music.play()  # Start playing the song
            time.sleep(1)  # Wait for 1 seconds
            pygame.mixer.music.stop()  # Stop the song after 1 seconds
        except pygame.error as e:
            print(f"Failed to play tot.mp3: {e}")

    def play_alarm_sound(self):
        """Play the farewell.mp3 song for 10 seconds when the door is unlocked."""
        try:
            pygame.mixer.music.load("alarm-2.mp3")  # Load the MP3 file
            pygame.mixer.music.play()  # Start playing the song
            time.sleep(10)  # Wait for 10 seconds
            pygame.mixer.music.stop()  # Stop the song after 11 seconds
        except pygame.error as e:
            print(f"Failed to play alarm.mp3: {e}")

    def update_door_status(self, fingerprint_id, status):
        """
        Update the door status (open/close) by making an API request.
        :param fingerprint_id: The fingerprint ID that was matched
        :param status: The new door status ('open' or 'close')
        """
        try:
            # Construct the URL with fingerprint_id and status
            url = f'{API_URL}/door/log-status?fingerprint_id={fingerprint_id}&status={status}'
            response = requests.post(url)
            response.raise_for_status()

            # Check if the API response contains a success message
            if response.status_code == 200:
                data = response.json()
                log_info = data.get('log', {})
                print(f"Door {status} successfully: {log_info}")
                # You can further extract and use details from the log (e.g., instructor name, log time)
            else:
                print(f"Failed to update door status: {response.status_code}")

        except requests.RequestException as e:
            print(f"API request failed: {e}")

    def auto_scan_fingerprint(self):
        failed_attempts = 0  # Initialize the counter for failed attempts

        while self.running:
            if not self.finger:
                return

            # Check for the 2-minute delay
            current_time = datetime.now()
            if self.last_scan_time:
                elapsed_time = (current_time - self.last_scan_time).total_seconds()
                if elapsed_time < 120:  # 120 seconds = 2 minutes
                    time.sleep(1)  # Sleep for a short duration to avoid busy-waiting
                    continue  # Skip to the next iteration to wait for the delay

            self.update_result("Waiting for fingerprint image...", color="green")
            self.speak("Waiting for fingerprint")  # Announce that the system is waiting for a fingerprint

            while self.finger.get_image() != adafruit_fingerprint.OK:
                if not self.running:
                    return
                time.sleep(1)

            print("Templating fingerprint...")
            if self.finger.image_2_tz(1) != adafruit_fingerprint.OK:
                print("Failed to template the fingerprint image.")
                failed_attempts += 1
                self.check_failed_attempts(failed_attempts)  # Check failed attempts and trigger the buzzer if needed
                time.sleep(3)
                continue

            # Search for fingerprint match and get the fingerprint ID
            if self.finger.finger_search() != adafruit_fingerprint.OK:
                # If fingerprint search fails, no match is found
                self.update_result("No matching fingerprint found.", color="red")
                self.play_wrong_song()  # Play the song when the door is unlocked
                self.speak("No matching fingerprint found. Please try again.")
                failed_attempts += 1
                self.check_failed_attempts(failed_attempts)
                time.sleep(3)
                continue

            # Reset failed attempts if successful
            failed_attempts = 0

            # Get the fingerprint ID after a successful match
            fingerprint_id = self.finger.finger_id
            print(f"Fingerprint ID detected: {fingerprint_id}")

            # Fetch user details from the database
            name = self.get_user_details(fingerprint_id)

            if not name:
                self.update_result("No matching fingerprint found in the database.", color="red")
                self.speak("No matching fingerprint found in the database.")
                self.play_wrong_song()  # Play the song when the door is unlocked
                time.sleep(3)
                continue

            print(f"User {name} found in the database.")

            # Update the last scan time
            self.last_scan_time = current_time

            # Determine if we should skip the schedule check and time-in/time-out for superusers
            is_superuser = fingerprint_id in [1, 2]

            if is_superuser:
                print("Superuser detected. Bypassing time-in/time-out process but allowing door control.")

                if self.is_manual_unlock:
                   # self.lock_door()
                    self.update_door_status(fingerprint_id, 'close')
                    self.is_manual_unlock = False
                    self.update_result(f"Goodbye, {name}! Door locked.", color="green")
                    self.speak(f"Goodbye {name}. The door is locked.")
                    self.play_welcome_song()  # Play the song when the door is locked
                else:
#                   self.unlock_door()
                    self.update_door_status(fingerprint_id, 'open')
                    self.is_manual_unlock = True
                    self.update_result(f"Welcome, {name}! Door unlocked.", color="green")
                    self.speak(f"Welcome {name}. The door is unlocked.")
                    self.play_welcome_song()  # Play the song when the door is unlocked
            else:
                print(
                    f"Fingerprint belongs to ordinary user with ID: {fingerprint_id}. Proceeding with schedule check...")
                is_makeup_class = self.check_if_makeup_class(fingerprint_id)

                if is_makeup_class:
                    schedule_check = self.get_schedule_mock_up(fingerprint_id)
                else:
                    schedule_check = self.get_schedule(fingerprint_id)

                if not schedule_check:
                    self.update_result("Access denied: Outside of allowed schedule.", color="red")
                    self.speak("Access denied. You are outside of your allowed schedule.")
                    self.play_wrong_song()  # Play the song when the door is unlocked
                    time.sleep(3)
                    continue

                current_time_data = self.fetch_current_date_time()
                if not current_time_data:
                    return
                current_time = datetime.strptime(current_time_data['current_time'], "%H:%M")

                if not self.check_time_in_record_fingerprint(fingerprint_id):
                    self.record_time_in_fingerprint(fingerprint_id, name)
                    # self.unlock_door()

                    # Update door status to 'open' using the API
                    self.update_door_status(fingerprint_id, 'open')

                    self.is_manual_unlock = True
                    self.last_time_in[fingerprint_id] = current_time
                    self.update_result(f"Welcome, {name}! Door unlocked.", color="green")
                    self.speak(f"Welcome {name}. The door is unlocked.")
                    self.play_welcome_song()  # Play the song when the door is unlocked

                    # # Update door status to 'open' using the API
                    # self.update_door_status(fingerprint_id, 'open')
                else:
                    self.record_time_out_fingerprint(fingerprint_id)
                    # self.lock_door()

                    # Update door status to 'close' using the API
                    self.update_door_status(fingerprint_id, 'close')
                    self.is_manual_unlock = False
                    self.record_all_time_out()
                    self.update_result(f"Goodbye, {name}! Door locked.", color="green")
                    self.speak(f"Goodbye {name}. The door is locked.")
                    self.play_welcome_song()  # Play the song when the door is locked

                    # # Update door status to 'close' using the API
                    # self.update_door_status(fingerprint_id, 'close')

                time.sleep(3)

    def check_if_makeup_class(self, fingerprint_id):
        # Replace with your logic to determine if this is a make-up class or not
        # Example: Fetch schedule and check the 'is_makeup_class' field
        try:
            response = requests.get(f"{LAB_SCHEDULE_FINGERPRINT_URL}{fingerprint_id}")
            response.raise_for_status()
            schedules = response.json()

            for schedule in schedules:
                if schedule.get('is_makeup_class') == 1:
                    return True
            return False
        except requests.RequestException as e:
            print("Request Error", f"Failed to check for make-up class: {e}")
            return False

    def check_failed_attempts(self, failed_attempts):
        if failed_attempts >= 3:
            self.update_result("Three or more consecutive failed attempts detected. Activating buzzer for 10 seconds.", color="red")
            self.play_alarm_sound()  # Play the song when the door is unlocked
            self.trigger_buzzer()
            failed_attempts = 0

    def trigger_buzzer(self):
        for _ in range(50):  # 5 seconds with 0.1-second intervals
            GPIO.output(BUZZER_PIN, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            time.sleep(0.1)

    def record_all_time_out(self):
        try:
            response = requests.get(RECENT_LOGS_URL)
            response.raise_for_status()
            logs = response.json()

            for log in logs:
                uid = log.get('UID')
                if log.get('time_in') and not log.get('time_out') and uid:
                    default_time_out = "00:00"
                    url = f"{TIME_OUT_URL}?rfid_number={uid}&time_out={default_time_out}"
                    response = requests.put(url)
                    response.raise_for_status()
                    print(f"Time-Out recorded for UID {uid} at {default_time_out}.")

            self.refresh_logs_table()

        except requests.RequestException as e:
            print(f"Error updating default time-out records: {e}")

    def refresh_logs_table(self):
        self.root.after(100, self.fetch_recent_logs)

    def fetch_recent_logs(self):
        try:
            response = requests.get(RECENT_LOGS_URL)
            response.raise_for_status()
            logs = response.json()

            # Clear the logs table before inserting new data
            for i in self.logs_tree.get_children():
                self.logs_tree.delete(i)

            # Insert logs with the latest first
            for log in reversed(logs):  # Reverse the logs to display the latest on top
                self.logs_tree.insert("", "end", values=(
                    log.get('date', 'N/A'),
                    log.get('user_name', 'N/A'),
                    log.get('seat_id', 'N/A'),
                    log.get('user_number', 'N/A'),
                    log.get('year', 'N/A'),
                    log.get('block_name', 'N/A'),
                    log.get('assigned_instructor', 'N/A'),
                    log.get('time_in', 'N/A'),
                    log.get('time_out', 'N/A')
                ))
        except requests.RequestException as e:
            self.update_result(f"Error fetching recent logs: {e}", color="red")

    def read_nfc_loop(self):
        while self.running:
            try:
                tag = self.clf.connect(rdwr={'on-connect': lambda tag: False})
                if tag:

                    self.play_tot_sound()  # Play the song when the smart card is tap

                    uid = tag.identifier.hex()
                    self.fetch_user_info(uid)
                    time.sleep(1)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)

    def fetch_user_info(self, uid):
        try:
            url = f'{USER_INFO_URL}?id_card_id={uid}'
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            self.student_number_entry.delete(0, tk.END)
            self.student_number_entry.insert(0, data.get('user_number', 'None'))

            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, data.get('user_name', 'None'))

            self.year_entry.delete(0, tk.END)
            self.year_entry.insert(0, data.get('year', 'None'))

            self.section_entry.delete(0, tk.END)
            self.section_entry.insert(0, data.get('block', 'None'))

            self.error_label.config(text="")

            # Clear entries after 3 seconds
            self.root.after(3000, self.clear_entries)

            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                return

            current_time = datetime.strptime(current_time_data['current_time'], "%H:%M")

            if self.check_time_in_record(uid):
                self.record_time_out(uid)
            else:
                self.record_time_in(uid, data.get('user_name', 'None'), data.get('year', 'None'))
                self.last_time_in[uid] = current_time

        except requests.HTTPError as http_err:
            if response.status_code == 404:
                self.clear_data()
                self.update_result("Card is not registered, Please contact the administrator.", color="red")
            else:
                self.update_result(f"HTTP error occurred: {http_err}", color="red")
        except requests.RequestException as e:
            self.update_result(f"Error fetching user info: {e}", color="red")

    def clear_entries(self):
        """Clear the entries for Student Number, Name, Year, and Section."""
        self.student_number_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.year_entry.delete(0, tk.END)
        self.section_entry.delete(0, tk.END)

    def check_time_in_record(self, rfid_number):
        try:
            url = f'{RECENT_LOGS_URL2}?rfid_number={rfid_number}'
            response = requests.get(url)
            response.raise_for_status()
            logs = response.json()
            return any(log.get('time_in') and not log.get('time_out') for log in logs)
        except requests.RequestException as e:
            self.update_result(f"Error checking Time-In record: {e}", color="red")
            return False

    def record_time_in(self, rfid_number, user_name, year):
        # Check if the class is a make-up class or a regular class
        is_makeup_class = self.check_if_makeup_class_rfid(rfid_number)

        if is_makeup_class:
            schedule_check = self.get_rfid_schedule_mock_up(rfid_number)
        else:
            schedule_check = self.get_rfid_schedule(rfid_number)

        if not schedule_check:
            self.update_result("Access denied: Not within scheduled time.", color="red")
            self.play_wrong_song()  # Play the song when the door is unlocked
            return

        try:
            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                return
            url = f"{TIME_IN_URL}?rfid_number={rfid_number}&time_in={current_time_data['current_time']}&year={year}&user_name={user_name}&role_id=3"
            response = requests.put(url)
            response.raise_for_status()

            print("Time-In recorded successfully.")
            self.update_result("Time-In recorded successfully.", color="green")
            self.fetch_recent_logs()
        except requests.RequestException as e:
            self.update_result(f"Error recording Time-In: {e}", color="red")

    def record_time_out(self, rfid_number):
        # Check if the class is a make-up class or a regular class
        is_makeup_class = self.check_if_makeup_class_rfid(rfid_number)

        if is_makeup_class:
            schedule_check = self.get_rfid_schedule_mock_up(rfid_number)
        else:
            schedule_check = self.get_rfid_schedule(rfid_number)

        if not schedule_check:
            self.update_result("Access denied: Not within scheduled time.", color="red")
            self.play_wrong_song()  # Play the song when the door is unlocked

        try:
            current_time_data = self.fetch_current_date_time()
            if not current_time_data:
                return
            if not self.check_time_in_record(rfid_number):
                self.update_result("No Time-In record found for this RFID. Cannot record Time-Out.", color="red")
                return

            url = f"{TIME_OUT_URL}?rfid_number={rfid_number}&time_out={current_time_data['current_time']}"
            response = requests.put(url)
            response.raise_for_status()
            print("Time-Out recorded successfully.")
            self.update_result("Time-Out recorded successfully.", color="green")
            self.fetch_recent_logs()
        except requests.RequestException as e:
            self.update_result(f"Error recording Time-Out: {e}", color="red")

    def clear_data(self):
        self.student_number_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.year_entry.delete(0, tk.END)
        self.section_entry.delete(0, tk.END)
        self.error_label.config(text="")

    def update_result(self, message, color="green"):
        """Update the result label with a message and specified color."""
        self.error_label.config(text=message, fg=color)  # Set the text and color
        self.root.after(3000, self.clear_result)  # Schedule to clear the message after 3 seconds

    def clear_result(self):
        self.error_label.config(text="")  # Clear the message

    def on_closing(self):
        self.running = False
        if self.nfc_thread.is_alive():
            self.nfc_thread.join()
        if self.fingerprint_thread.is_alive():
            self.fingerprint_thread.join()
        if self.clf is not None:
            self.clf.close()
        self.root.destroy()


# Create the main window
root = tk.Tk()
app = AttendanceApp(root)

center_window(root, 1200, 800)

# Run the application
root.mainloop()
