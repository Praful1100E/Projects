import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from datetime import datetime
import os
from ttkbootstrap import Style

# Create data directory if not exists
if not os.path.exists("data"):
    os.makedirs("data")

# Excel file path
excel_file = "data/attendance_log.xlsx"

# Initialize Excel file
if not os.path.exists(excel_file):
    df_init = pd.DataFrame(columns=["Date", "Time", "Roll Number", "Name", "Action"])
    df_init.to_excel(excel_file, index=False)

# Load student list (can be expanded)
students = {
    "101": "Aman Sharma",
    "102": "Priya Mehta",
    "103": "Rahul Verma",
    "104": "Sonal Kapoor"
}

# Main app
class GateAttendanceApp:
    def _init_(self, root):
        self.root = root
        self.root.title("Gate Attendance System")
        self.root.geometry("500x400")
        Style("darkly")  # Use dark theme

        self.label = ttk.Label(root, text="Gate Attendance System", font=("Helvetica", 20))
        self.label.pack(pady=20)

        self.roll_label = ttk.Label(root, text="Select Roll Number:")
        self.roll_label.pack()

        self.roll_var = tk.StringVar()
        self.roll_menu = ttk.Combobox(root, textvariable=self.roll_var, values=list(students.keys()), state="readonly")
        self.roll_menu.pack(pady=10)

        self.name_label = ttk.Label(root, text="Name will be auto-filled", foreground="gray")
        self.name_label.pack()

        self.button_frame = ttk.Frame(root)
        self.button_frame.pack(pady=20)

        self.in_button = ttk.Button(self.button_frame, text="Gate IN", bootstyle="success", command=self.mark_in)
        self.in_button.grid(row=0, column=0, padx=10)

        self.out_button = ttk.Button(self.button_frame, text="Gate OUT", bootstyle="danger", command=self.mark_out)
        self.out_button.grid(row=0, column=1, padx=10)

        self.view_button = ttk.Button(root, text="View Today's Log", bootstyle="info", command=self.view_log)
        self.view_button.pack(pady=10)

        self.root.bind("<<ComboboxSelected>>", self.update_name)

    def update_name(self, event=None):
        roll = self.roll_var.get()
        if roll in students:
            self.name_label.config(text=f"Name: {students[roll]}")
        else:
            self.name_label.config(text="Name will be auto-filled")

    def mark_attendance(self, action):
        roll = self.roll_var.get()
        if not roll:
            messagebox.showerror("Error", "Please select a Roll Number!")
            return

        name = students.get(roll, "Unknown")
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        df = pd.read_excel(excel_file)
        new_entry = {
            "Date": date_str,
            "Time": time_str,
            "Roll Number": roll,
            "Name": name,
            "Action": action
        }
        df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
        df.to_excel(excel_file, index=False)

        messagebox.showinfo("Success", f"{action} recorded for {name} at {time_str}")

    def mark_in(self):
        self.mark_attendance("Gate IN")

    def mark_out(self):
        self.mark_attendance("Gate OUT")

    def view_log(self):
        df = pd.read_excel(excel_file)
        today = datetime.now().strftime("%Y-%m-%d")
        df_today = df[df["Date"] == today]

        top = tk.Toplevel(self.root)
        top.title("Today's Log")
        top.geometry("600x300")

        tree = ttk.Treeview(top, columns=list(df.columns), show="headings")
        for col in df.columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        for _, row in df_today.iterrows():
            tree.insert("", tk.END, values=list(row))
        tree.pack(fill=tk.BOTH, expand=True)

# Run app
if __name__ == "__main__":
    root = tk.Tk()
    app = GateAttendanceApp(root)
    root.mainloop()