import tkinter as tk
from tkinter import messagebox
from ttkbootstrap import Style
from ttkbootstrap.widgets import Entry, Button
import os

TASK_FILE = "tasks.txt"

class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🗒️ Dark To-Do List")
        self.root.geometry("400x500")
        self.root.resizable(False, False)

        # Apply dark theme
        self.style = Style(theme="darkly")

        # Task Entry
        self.task_var = tk.StringVar()
        self.entry = Entry(self.root, textvariable=self.task_var, font=("Segoe UI", 12), width=30)
        self.entry.pack(pady=10)

        # Add Task Button
        self.add_btn = Button(self.root, text="Add Task", command=self.add_task, bootstyle="success")
        self.add_btn.pack(pady=5)

        # Task List
        self.listbox = tk.Listbox(self.root, font=("Segoe UI", 12), height=15, bg="#212529", fg="#f8f9fa", selectbackground="#0d6efd")
        self.listbox.pack(pady=10, fill=tk.BOTH, padx=20)

        # Buttons
        self.delete_btn = Button(self.root, text="Delete Selected", command=self.delete_task, bootstyle="danger")
        self.delete_btn.pack(pady=5)

        self.clear_btn = Button(self.root, text="Clear All", command=self.clear_tasks, bootstyle="warning")
        self.clear_btn.pack(pady=5)

        self.save_btn = Button(self.root, text="Save Tasks", command=self.save_tasks, bootstyle="info")
        self.save_btn.pack(pady=5)

        # Load previous tasks
        self.load_tasks()

    def add_task(self):
        task = self.task_var.get().strip()
        if task:
            self.listbox.insert(tk.END, task)
            self.task_var.set("")
        else:
            messagebox.showwarning("Empty Entry", "Please enter a task.")

    def delete_task(self):
        try:
            index = self.listbox.curselection()[0]
            self.listbox.delete(index)
        except IndexError:
            messagebox.showerror("Error", "No task selected.")

    def clear_tasks(self):
        if messagebox.askyesno("Clear All", "Are you sure you want to clear all tasks?"):
            self.listbox.delete(0, tk.END)

    def save_tasks(self):
        tasks = self.listbox.get(0, tk.END)
        with open(TASK_FILE, "w") as f:
            for task in tasks:
                f.write(task + "\n")
        messagebox.showinfo("Saved", "Tasks saved successfully!")

    def load_tasks(self):
        if os.path.exists(TASK_FILE):
            with open(TASK_FILE, "r") as f:
                for line in f:
                    task = line.strip()
                    if task:
                        self.listbox.insert(tk.END, task)

# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()
