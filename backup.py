def get_schedule(fingerprint_id):
    try:
        response = requests.get(f"https://prolocklogger.pro/api/lab-schedules/fingerprint/{fingerprint_id}")
        if response.status_code == 200:
            schedules = response.json()
            if schedules:
                today = datetime.now().strftime('%A')  # Get the current day of the week
                current_time = datetime.now().strftime('%H:%M')  # Get the current time
                for schedule in schedules:
                    if schedule['day_of_the_week'] == today:
                        start_time = schedule['class_start']
                        end_time = schedule['class_end']
                        if start_time <= current_time <= end_time:
                            return True  # Schedule matches, allow access
            return False  # No matching schedule or not within allowed time
        else:
            messagebox.showerror("API Error", "Failed to fetch schedule from API.")
            return False
    except requests.RequestException as e:
        messagebox.showerror("Request Error", f"Failed to connect to API: {e}")
        return False

def auto_scan_fingerprint():
    global unlock_attempt

    if not finger:
        return

    print("Waiting for image...")
    while finger.get_image() != adafruit_fingerprint.OK:
        pass

    print("Templating...")
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        messagebox.showwarning("Error", "Failed to template the fingerprint image.")
        root.after(5000, auto_scan_fingerprint)  # Retry after 5 seconds
        return
    print("Searching...")
    if finger.finger_search() != adafruit_fingerprint.OK:
        messagebox.showwarning("Error", "Failed to search for fingerprint match.")
        root.after(5000, auto_scan_fingerprint)  # Retry after 5 seconds
        return

    print("Detected #", finger.finger_id, "with confidence", finger.confidence)

    # Fetch user details using API
    name = get_user_details(finger.finger_id)

    if name:
        if get_schedule(finger.finger_id):  # Check if the current time is within the allowed schedule
            if not check_time_in_record(finger.finger_id):
                # Record Time-In, unlock door, and transition to RFID scanning
                record_time_in(finger.finger_id, name)
                unlock_door()
                messagebox.showinfo("Welcome", f"Welcome, {name}! Door unlocked.")
                root.after(1000, run_rfid_script)  # Wait 1 second then run RFID script
            else:
                # Record Time-Out and lock door
                record_time_out(finger.finger_id)
                lock_door()
                messagebox.showinfo("Goodbye", f"Goodbye, {name}! Door locked.")
                root.after(10000, auto_scan_fingerprint)  # Wait 10 seconds then resume scanning
        else:
            messagebox.showinfo("Access Denied", "Access is not allowed outside of scheduled times.")
    else:
        messagebox.showinfo("No Match", "No matching fingerprint found in the database.")
