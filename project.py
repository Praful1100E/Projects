import os
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import pandas as pd

# ✅ Step 1: Excel file path
EXCEL_PATH = r"C:\Users\rajpu\Downloads\(coppy).xlsx"

# ✅ Step 2: Load attendance sheet
def load_attendance_data():
    if os.path.exists(EXCEL_PATH):
        df = pd.read_excel(EXCEL_PATH)
        print("Excel Columns:", df.columns.tolist())  # Enhanced debugging
        return df
    else:
        messagebox.showerror("File Not Found", "Excel file not found.")
        return pd.DataFrame()

# ✅ Step 3: Save updated sheet
def save_attendance_data(df):
    df.to_excel(EXCEL_PATH, index=False)

# ✅ Step 4: Toggle attendance on click
def toggle_attendance(event):
    selected_item = tree.selection()
    if not selected_item:
        return

    item = tree.item(selected_item)
    roll = item['values'][0]  # Roll number is the first column
    today = datetime.today().strftime('%d-%b').lower()  # e.g., '24-Jul' -> '24-jul'
    df = load_attendance_data()

    if today not in df.columns:
        df[today] = ""

    matched = df[df['Roll number'] == int(roll)]  # Use exact column name
    if not matched.empty:
        index = matched.index[0]
        current_status = df.at[index, today]
        new_status = "P" if current_status != "P" else "A"  # Match 'P' and 'A' from sheet
        df.at[index, today] = new_status
        save_attendance_data(df)
        tree.item(selected_item, values=(roll, matched['Name'].iloc[0], new_status))
        messagebox.showinfo("Success", f"Attendance for Roll No {roll} set to {new_status}")

# ✅ Step 5: GUI Setup
root = tk.Tk()
root.title("🎓 Mark Attendance by Roll Number")
root.geometry("600x400")
root.configure(bg="#222")

# Load Data
df_main = load_attendance_data()

# ✅ Step 6: Detect roll number and name column
roll_column_name = "Roll number"  # Exact column name from sheet
name_column_name = "Name"  # Exact column name from sheet

if roll_column_name not in df_main.columns or name_column_name not in df_main.columns:
    messagebox.showerror("Error", f"No valid roll number or name column found in Excel file. Detected columns: {df_main.columns.tolist()}")
    root.destroy()
else:
    # Treeview setup
    tree_frame = tk.Frame(root, bg="#222")
    tree_frame.pack(pady=10, fill="both", expand=True)

    tree = ttk.Treeview(tree_frame, columns=("Roll", "Name", "Status"), show="headings")
    tree.heading("Roll", text="Roll Number")
    tree.heading("Name", text="Name")
    tree.heading("Status", text="Attendance")
    tree.column("Roll", width=100)
    tree.column("Name", width=200)
    tree.column("Status", width=100)
    
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Populate Treeview
    today = datetime.today().strftime('%d-%b').lower()  # Match date format (e.g., '24-jul')
    for _, row in df_main.iterrows():
        roll = str(int(row[roll_column_name]))
        name = row[name_column_name]
        status = row.get(today, "")
        tree.insert("", "end", values=(roll, name, status))

    # Bind click event
    tree.bind("<Double-1>", toggle_attendance)

    tk.Label(root, text="Double-click a student to toggle Present/Absent", 
             font=("Arial", 10), bg="#222", fg="gray").pack(pady=10)
    tk.Label(root, text="📁 Attendance saved in Excel file", 
             font=("Arial", 10), bg="#222", fg="gray").pack(pady=10)

    root.mainloop()