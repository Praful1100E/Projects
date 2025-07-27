import os
import json
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from ttkbootstrap import Style
from ttkbootstrap.constants import *
import pandas as pd

EXCEL_FILE = "Attendance_Records.xlsx"
JSON_FILE = "students.json"

def load_students():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r') as f:
            return json.load(f)
    return []

def save_students(student_list):
    with open(JSON_FILE, 'w') as f:
        json.dump(student_list, f, indent=2)

def load_or_create_excel():
    if os.path.exists(EXCEL_FILE):
        return pd.read_excel(EXCEL_FILE)
    else:
        df = pd.DataFrame(columns=["Roll Number", "Name"])
        df.to_excel(EXCEL_FILE, index=False)
        return df

def main():
    # --- Functions inside main ---

    def update_display():
        student_listbox.delete(0, tk.END)
        for student in student_list:
            student_listbox.insert(tk.END, f"{student['roll']} - {student['name']}")
        count_label.config(text=f"Total Students: {len(student_list)}")

    def add_student():
        name = name_entry.get().strip()
        roll = roll_entry.get().strip()
        if name and roll:
            if not any(s["roll"] == roll for s in student_list):
                student_list.append({"name": name, "roll": roll})
                save_students(student_list)
                name_entry.delete(0, tk.END)
                roll_entry.delete(0, tk.END)
                update_display()
            else:
                messagebox.showerror("Duplicate", "Roll number already exists!")

    def add_multiple_students():
        data = bulk_text.get("1.0", tk.END).strip()
        if not data:
            messagebox.showwarning("Input Missing", "Enter student data in 'Roll, Name' format.")
            return

        lines = data.split("\n")
        added = 0
        for line in lines:
            if ',' in line:
                parts = line.split(',')
                roll = parts[0].strip()
                name = parts[1].strip()
                if roll and name and not any(s["roll"] == roll for s in student_list):
                    student_list.append({"name": name, "roll": roll})
                    added += 1

        if added > 0:
            save_students(student_list)
            update_display()
            bulk_text.delete("1.0", tk.END)
            messagebox.showinfo("Success", f"{added} students added.")
        else:
            messagebox.showwarning("No Student Added", "No new valid students found.")

    def remove_student():
        selected = student_listbox.curselection()
        if selected:
            del student_list[selected[0]]
            save_students(student_list)
            update_display()

    def mark_attendance():
        selected = student_listbox.curselection()
        if not selected:
            messagebox.showwarning("No selection", "Please select at least one student.")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        df = load_or_create_excel()

        if today not in df.columns:
            df[today] = "Absent"

        roll_numbers = [student_list[i]["roll"] for i in selected]

        for roll in roll_numbers:
            idx = df.index[df["Roll Number"] == roll]
            if not idx.empty:
                df.at[idx[0], today] = "Present"
            else:
                name = next((s["name"] for s in student_list if s["roll"] == roll), "Unknown")
                new_row = {"Roll Number": roll, "Name": name, today: "Present"}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        df.to_excel(EXCEL_FILE, index=False)
        update_display()
        messagebox.showinfo("Success", "Attendance marked successfully.")

    # --- GUI Setup ---
    root = tk.Tk()
    root.title("🎓 Student Attendance System")
    root.geometry("600x750")

    Style(theme="darkly")

    global student_list
    student_list = load_students()

    # Title
    tk.Label(root, text="📋 Attendance System", font=("Helvetica", 18, "bold")).pack(pady=15)

    # Entry Fields
    tk.Label(root, text="Name:", font=("Arial", 12)).pack()
    name_entry = tk.Entry(root, font=("Arial", 12), width=30)
    name_entry.pack(pady=5)

    tk.Label(root, text="Roll Number:", font=("Arial", 12)).pack()
    roll_entry = tk.Entry(root, font=("Arial", 12), width=30)
    roll_entry.pack(pady=5)

    # Buttons
    frame_btn = tk.Frame(root)
    frame_btn.pack(pady=10)
    tk.Button(frame_btn, text="➕ Add Student", command=add_student, width=15).grid(row=0, column=0, padx=5)
    tk.Button(frame_btn, text="❌ Remove Student", command=remove_student, width=15).grid(row=0, column=1, padx=5)
    tk.Button(frame_btn, text="✅ Mark Attendance", command=mark_attendance, width=20).grid(row=0, column=2, padx=5)

    # Bulk Add
    tk.Label(root, text="OR", font=("Arial", 11, "bold")).pack(pady=5)
    tk.Label(root, text="📥 Bulk Add (Roll, Name):", font=("Arial", 12)).pack()
    bulk_text = tk.Text(root, height=5, width=50, font=("Arial", 11))
    bulk_text.pack(pady=5)
    tk.Button(root, text="➕ Add Multiple Students", command=add_multiple_students, width=25).pack(pady=5)

    # Student List
    tk.Label(root, text="🎯 Select Students for Attendance", font=("Arial", 12, "bold")).pack(pady=10)
    student_listbox = tk.Listbox(root, height=15, width=50, font=("Arial", 12), selectmode=tk.MULTIPLE,
                                 bg="#2e2e2e", fg="white", selectbackground="gray")
    student_listbox.pack()

    count_label = tk.Label(root, text="", font=("Arial", 11))
    count_label.pack(pady=5)

    # Footer
    tk.Label(root, text="Made with ❤ using Python + Tkinter + Excel", font=("Arial", 9)).pack(pady=20)

    update_display()
    root.mainloop()

if __name__ == "__main__":
    main()