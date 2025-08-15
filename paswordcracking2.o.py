import os
import threading
import itertools
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PyPDF2 import PdfReader

# --- Global Variables ---
selected_pdf = None
stop_flag = False

def select_pdf():
    global selected_pdf
    file_path = filedialog.askopenfilename(
        title="Select Locked PDF",
        filetypes=[("PDF Files", "*.pdf")]
    )
    if file_path:
        selected_pdf = file_path
        lbl_status.config(text=f"Selected: {os.path.basename(file_path)}", fg="green")

def numbers_only_bruteforce():
    """Brute-force: numbers only, up to selected max length."""
    global stop_flag
    if not selected_pdf:
        messagebox.showerror("Error", "Please select a PDF file first.")
        return

    chars = "0123456789"  # numbers only
    max_length = int(combo_length.get())  # from dropdown
    stop_flag = False
    lbl_status.config(text=f"Brute-forcing 0-9 up to {max_length} digits...", fg="blue")

    def crack():
        try:
            reader = PdfReader(selected_pdf)
            for length in range(1, max_length + 1):
                for combo in itertools.product(chars, repeat=length):
                    if stop_flag:
                        lbl_status.config(text="Stopped.", fg="orange")
                        return
                    password = ''.join(combo)
                    if reader.decrypt(password):
                        lbl_status.config(text=f"Password Found: {password}", fg="green")
                        messagebox.showinfo("Success", f"Password Found: {password}")
                        return
            lbl_status.config(text="Password Not Found!", fg="red")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    threading.Thread(target=crack, daemon=True).start()

def stop_cracking():
    global stop_flag
    stop_flag = True

# --- Tkinter GUI ---
root = tk.Tk()
root.title("PDF Password Cracker - Numbers Only")
root.geometry("420x280")
root.resizable(False, False)

tk.Label(root, text="PDF Password Cracker (Numbers Only)", font=("Arial", 14, "bold")).pack(pady=10)

# Select PDF Button
tk.Button(root, text="Select Locked PDF", command=select_pdf, width=25).pack(pady=5)

# Dropdown for max length
frame_len = tk.Frame(root)
frame_len.pack(pady=5)
tk.Label(frame_len, text="Max Digits:").pack(side=tk.LEFT, padx=5)
combo_length = ttk.Combobox(frame_len, values=[1, 2, 3, 4, 5, 6], width=5)
combo_length.current(3)  # default to 4
combo_length.pack(side=tk.LEFT)

# Buttons
tk.Button(root, text="Start Numbers-Only Brute-Force", command=numbers_only_bruteforce, width=30, bg="red", fg="white").pack(pady=5)
tk.Button(root, text="Stop", command=stop_cracking, width=30, bg="orange").pack(pady=5)

# Status Label
lbl_status = tk.Label(root, text="No file selected.", fg="gray")
lbl_status.pack(pady=20)

root.mainloop()
