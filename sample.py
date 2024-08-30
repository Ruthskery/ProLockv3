import tkinter as tk
import os
import time

def main():
    root = tk.Tk()
    root.title("2.py - Timer Window")
    root.geometry("400x200")

    label = tk.Label(root, text="Window will close and restart 1.py in 5 seconds...", font=("Arial", 14))
    label.pack(pady=50)

    # Function to close the Tkinter window and restart 1.py
    def on_timeout():
        print("5 seconds passed. Closing window and restarting 1.py...")
        root.quit()  # Stop the Tkinter main loop
        root.destroy()  # Destroy the window
        os.system('python 1.py')  # Restart 1.py

    # Set a timer to call on_timeout() after 5 seconds
    root.after(5000, on_timeout)

    root.mainloop()

if __name__ == "__main__":
    main()
