import tkinter as tk
from tkinter import font, ttk
from datetime import datetime
import nfc
import threading
import time
import requests
import subprocess

# Replace these URLs with your actual Laravel API URLs
USER_INFO_URL = 'https://prolocklogger.pro/api/user-information/by-id-card'
RECENT_LOGS_URL = 'https://prolocklogger.pro/api/recent-logs'
TIME_IN_URL = 'https://prolocklogger.pro/api/logs/time-in'
TIME_OUT_URL = 'https://prolocklogger.pro/api/logs/time-out'
RECENT_LOGS_URL2 = 'https://prolocklogger.pro/api/recent-logs/by-uid'

class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RFID Scanning and Attendance")
        self.root.geometry("1000x450")  # Adjust window size

        # Define custom fonts
        heading_font = font.Font(family="Helvetica", size=16, weight="bold")
        label_font = font.Font(family="Helvetica", size=12)
        clock_font = font.Font(family="Helvetica", size=14)

        # Function to update the clock
        self.clock_label = tk.Label(root, font=clock_font)
        self.clock_label.pack(pady=10)
        self.update_clock()  # Initialize the clock

        # Create the main heading
        main_heading = tk.Label(root, text="Student Attendance Monitoring", font=heading_font)
        main_heading.pack(pady=10)

        # Student Information Frame
        info_frame = tk.Frame(root)
        info_frame.pack(pady=10)

        # Student Number
        student_number_label = tk.Label(info_frame, text="Student Number:", font=label_font)
        student_number_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')
        self.student_number_entry = tk.Entry(info_frame, font=label_font)
        self.student_number_entry.grid(row=0, column=1, padx=10, pady=5)

        # Name
        name_label = tk.Label(info_frame, text="Name:", font=label_font)
        name_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.name_entry = tk.Entry(info_frame, font=label_font)
        self.name_entry.grid(row=1, column=1, padx=10, pady=5)

        # Year
        year_label = tk.Label(info_frame, text="Year:", font=label_font)
        year_label.grid(row=2, column=0, padx=10, pady=5, sticky='w')
        self.year_entry = tk.Entry(info_frame, font=label_font)
        self.year_entry.grid(row=2, column=1, padx=10, pady=5)

        # Section
        section_label = tk.Label(info_frame, text="Section:", font=label_font)
        section_label.grid(row=3, column=0, padx=10, pady=5, sticky='w')
        self.section_entry = tk.Entry(info_frame, font=label_font)
        self.section_entry.grid(row=3, column=1, padx=10, pady=5)

        # Error Message Label
        self.error_label = tk.Label(root, text="", font=("Helvetica", 10, "bold", "italic"), foreground="red")
        self.error_label.pack(pady=10)

        # Create the Treeview for logs
        columns = ("Student Name", "Block", "Year", "Time-In", "Time-Out")
        self.logs_tree = ttk.Treeview(root, columns=columns, show='headings')
        self.logs_tree.pack(pady=10, fill='both', expand=True)

        # Define column headings
        for col in columns:
            self.logs_tree.heading(col, text=col)
            self.logs_tree.column(col, minwidth=100, width=100, anchor='center')

        # Fetch and display recent logs
        self.fetch_recent_logs()

        # Initialize NFC reader
        self.clf = nfc.ContactlessFrontend('usb')
        self.running = True
        self.script_run = False  # Flag to indicate if the script has been run
        self.thread = threading.Thread(target=self.read_nfc_loop)
        self.thread.start()

        # Track time-ins and time-outs
        self.time_in_records = set()
        self.time_out_records = set()

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    def update_clock(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.clock_label.config(text=current_time)
        self.root.after(1000, self.update_clock)  # Update every 1 second

    def read_nfc_loop(self):
        while self.running:
            try:
                tag = self.clf.connect(rdwr={'on-connect': lambda tag: False})
                if tag:
                    uid = tag.identifier.hex()
                    self.fetch_user_info(uid)
                    time.sleep(1)

                # Check if the script has been run; if so, terminate the loop
                if self.script_run:
                    self.running = False
                    self.root.quit()  # Terminate the Tkinter main loop

            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)

    def fetch_user_info(self, uid):
        try:
            url = f'{USER_INFO_URL}?id_card_id={uid}'
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad status codes
            data = response.json()

            user_number = data.get('user_number') or 'None'
            user_name = data.get('user_name') or 'None'
            year = data.get('year') or 'None'
            block = data.get('block') or 'None'

            self.student_number_entry.delete(0, tk.END)
            self.student_number_entry.insert(0, user_number)
            
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, user_name)
            
            self.year_entry.delete(0, tk.END)
            self.year_entry.insert(0, year)
            
            self.section_entry.delete(0, tk.END)
            self.section_entry.insert(0, block)

            self.error_label.config(text="")  # Clear any previous error message

            if self.check_time_in_record(uid):
                self.record_time_out(uid)
            else:
                self.record_time_in(uid, user_name, year)

            self.update_records(uid)

            if self.all_time_ins_accounted_for():
                self.run_external_script()

        except requests.HTTPError as http_err:
            if response.status_code == 404:
                self.clear_data()
                self.update_result("Card is not registered, Please contact the administrator.")
            else:
                self.update_result(f"HTTP error occurred: {http_err}")
        except requests.RequestException as e:
            self.update_result(f"Error fetching user info: {e}")

    def update_records(self, uid):
        if self.check_time_in_record(uid):
            self.time_in_records.add(uid)
        else:
            self.time_out_records.add(uid)

    def all_time_ins_accounted_for(self):
        return self.time_in_records == self.time_out_records

    def run_external_script(self):
        try:
            subprocess.Popen(['python', 'debug_fingerprint.py'])
            self.script_run = True  # Set the flag to True after the script runs
        except Exception as e:
            self.update_result(f"Error running script: {e}")
            
    def check_time_in_record(self, rfid_number):
        try:
            url = f'{RECENT_LOGS_URL2}?rfid_number={rfid_number}'
            response = requests.get(url)
            response.raise_for_status()

            logs = response.json()
            for log in logs:
                if log.get('time_in') and not log.get('time_out'):
                    return True

            return False

        except requests.RequestException as e:
            self.update_result(f"Error checking Time-In record: {e}")
            return False

    def record_time_in(self, rfid_number, user_name, year):
        try:
            url = f"{TIME_IN_URL}?rfid_number={rfid_number}&time_in={datetime.now().strftime('%H:%M')}&year={year}&user_name={user_name}&role_id=3"
            response = requests.put(url)
            response.raise_for_status()
            result = response.json()
            print(result)
            self.update_result("Time-In recorded successfully.")
            self.fetch_recent_logs()

        except requests.RequestException as e:
            self.update_result(f"Error recording Time-In: {e}")

    def record_time_out(self, rfid_number):
        try:
            if not self.check_time_in_record(rfid_number):
                self.update_result("No Time-In record found for this RFID. Cannot record Time-Out.")
                return

            url = f"{TIME_OUT_URL}?rfid_number={rfid_number}&time_out={datetime.now().strftime('%H:%M')}"
            response = requests.put(url)
            response.raise_for_status()
            result = response.json()
            print(result)
            self.update_result("Time-Out recorded successfully.")
            self.fetch_recent_logs()

        except requests.RequestException as e:
            self.update_result(f"Error recording Time-Out: {e}")

    def fetch_recent_logs(self):
        try:
            response = requests.get(RECENT_LOGS_URL)
            response.raise_for_status()

            logs = response.json()

            # Clear existing logs
            for i in self.logs_tree.get_children():
                self.logs_tree.delete(i)

            # Insert new logs
            for log in logs:
                self.logs_tree.insert("", "end", values=(
                    log['user_name'],
                    log['block_name'],
                    log['year'],
                    log['time_in'],
                    log['time_out']
                ))

        except requests.RequestException as e:
            self.update_result(f"Error fetching recent logs: {e}")

    def clear_data(self):
        # Clear all entry fields
        self.student_number_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.year_entry.delete(0, tk.END)
        self.section_entry.delete(0, tk.END)

    def update_result(self, message):
        self.error_label.config(text=message)

    def on_closing(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
        if hasattr(self, 'clf') and self.clf is not None:
            self.clf.close()
        self.root.destroy()

    def __del__(self):
        if hasattr(self, 'clf') and self.clf is not None:
            self.clf.close()

# Create the main window
root = tk.Tk()
app = AttendanceApp(root)

# Run the application
root.mainloop()




