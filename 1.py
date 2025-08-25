import cv2
import face_recognition
import numpy as np
import os
import json
import urllib.request
import csv
from datetime import datetime, timedelta
from tkinter import Tk, Label, Entry, Button, StringVar, Frame, messagebox
from PIL import Image, ImageTk
import math
import time

# -----------------------
# Constants & paths
# -----------------------
KNOWN_FACE_DIR = "known_faces"
DATA_FILE = "face_data.json"
ATTENDANCE_FILE = "attendance_log.csv"
IP_FILE = "camera_ip.txt"

os.makedirs(KNOWN_FACE_DIR, exist_ok=True)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)
if not os.path.exists(ATTENDANCE_FILE):
    with open(ATTENDANCE_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Name', 'Mobile', 'Time'])
if not os.path.exists(IP_FILE):
    with open(IP_FILE, 'w') as f:
        f.write("http://192.0.0.4:8080/shot.jpg")

with open(IP_FILE, 'r') as f:
    CAMERA_URL = f.read().strip()

# -----------------------
# Theme (Dark + Cyan)
# -----------------------
BG = "#0b0f14"           # Dark background
BG_PANEL = "#101820"     # Panel background
FG = "#e6f1ff"           # Light foreground
ACCENT = "#00d1d1"       # Cyan accent
ACCENT_DARK = "#00a0a0"  # Darker cyan
BTN_BG = "#16212b"       # Button background
INPUT_BG = "#0f1720"     # Input background
WARN = "#ffcc00"
OK = "#16c79a"
ERR = "#ff5c5c"

# -----------------------
# Accuracy settings
# -----------------------
DIST_THRESHOLD = 0.45      # tighter than default ~0.6
MARGIN = 0.03              # require gap to next best
MIN_FACE_SIZE = 80         # min box size (pixels)
MIN_BLUR_VAR = 120.0       # Laplacian variance threshold
COOLDOWN_SECS = 120        # per-person cooldown
ENROLL_SHOTS = 5           # multi-shot capture
UPSCALE = 1                # face_locations upsample factor

# -----------------------
# Load known faces
# -----------------------
known_face_encodings = []
known_face_names = []
face_data = {}

with open(DATA_FILE, "r") as f:
    face_data = json.load(f)

def load_known_faces():
    known_face_encodings.clear()
    known_face_names.clear()
    for name, info in face_data.items():
        img_path = os.path.join(KNOWN_FACE_DIR, info['image'])
        if os.path.exists(img_path):
            image = face_recognition.load_image_file(img_path)
            encs = face_recognition.face_encodings(image)
            if encs:
                known_face_encodings.append(encs)
                known_face_names.append(name)

load_known_faces()

# -----------------------
# Helpers: quality, alignment, liveness hook
# -----------------------
def face_quality_ok(rgb_frame, box):
    top, right, bottom, left = box
    w = right - left
    h = bottom - top
    if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
        return False
    face_crop = rgb_frame[top:bottom, left:right]
    if face_crop.size == 0:
        return False
    gray = cv2.cvtColor(face_crop, cv2.COLOR_RGB2GRAY)
    blur_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return blur_var >= MIN_BLUR_VAR

def align_face_rough(rgb_frame, box):
    # Rough alignment placeholder: center-crop and resize
    top, right, bottom, left = box
    face = rgb_frame[top:bottom, left:right]
    if face.size == 0:
        return face
    # Resize to a canonical size to stabilize encodings
    return cv2.resize(face, (256, 256), interpolation=cv2.INTER_CUBIC)

def liveness_pass(rgb_frame, box):
    # Lightweight hook: return True for now; integrate EAR/texture later
    return True

# -----------------------
# Tkinter GUI
# -----------------------
root = Tk()
root.title("Face Attendance")
root.configure(bg=BG)

# Top frame
frame = Frame(root, bg=BG_PANEL, bd=0, highlightthickness=1, highlightbackground=ACCENT)
frame.pack(padx=10, pady=10, fill="x")

def style_label(widget):
    widget.configure(bg=BG_PANEL, fg=FG)

def style_entry(widget):
    widget.configure(bg=INPUT_BG, fg=FG, insertbackground=FG, highlightthickness=1, highlightbackground=ACCENT)

def style_button(widget):
    widget.configure(bg=BTN_BG, fg=FG, activebackground=ACCENT, activeforeground="#001015",
                     bd=0, highlightthickness=1, highlightbackground=ACCENT)

# Camera IP entry
camera_var = StringVar(value=CAMERA_URL)
lbl_ip = Label(frame, text="Camera IP:")
style_label(lbl_ip)
lbl_ip.grid(row=0, column=0, padx=6, pady=6, sticky="w")
camera_entry = Entry(frame, textvariable=camera_var, width=44)
style_entry(camera_entry)
camera_entry.grid(row=0, column=1, padx=6, pady=6)
def save_camera_ip():
    global CAMERA_URL
    CAMERA_URL = camera_var.get().strip()
    with open(IP_FILE, 'w') as f:
        f.write(CAMERA_URL)
    messagebox.showinfo("Saved", "Camera IP saved.")
btn_ip = Button(frame, text="Save IP", command=save_camera_ip)
style_button(btn_ip)
btn_ip.grid(row=0, column=2, padx=6, pady=6)

# Name & Mobile Entry
lbl_name = Label(frame, text="Name:")
style_label(lbl_name)
lbl_name.grid(row=1, column=0, padx=6, pady=6, sticky="w")
name_var = StringVar()
ent_name = Entry(frame, textvariable=name_var, width=30)
style_entry(ent_name)
ent_name.grid(row=1, column=1, padx=6, pady=6, sticky="w")

lbl_mobile = Label(frame, text="Mobile:")
style_label(lbl_mobile)
lbl_mobile.grid(row=2, column=0, padx=6, pady=6, sticky="w")
mobile_var = StringVar()
ent_mobile = Entry(frame, textvariable=mobile_var, width=30)
style_entry(ent_mobile)
ent_mobile.grid(row=2, column=1, padx=6, pady=6, sticky="w")

# Status label
status_var = StringVar()
status_label = Label(root, textvariable=status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 12, "bold"))
status_label.pack(pady=6)

# Video panel
video_frame = Frame(root, bg=BG_PANEL, bd=0, highlightthickness=1, highlightbackground=ACCENT)
video_frame.pack(padx=10, pady=10)
video_label = Label(video_frame, bg=BG_PANEL)
video_label.pack()

# Add Face button
def set_status(text, color=ACCENT):
    status_var.set(text)
    status_label.configure(fg=color)

# Multi-shot enroll with quality filtering
def capture_best_face_shots():
    shots = []
    deadline = time.time() + 8  # up to 8 seconds window
    while len(shots) < ENROLL_SHOTS and time.time() < deadline:
        frame = get_frame()
        if frame is None:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb, number_of_times_to_upsample=UPSCALE, model="hog")
        encs = face_recognition.face_encodings(rgb, boxes)
        for box, enc in zip(boxes, encs):
            if not face_quality_ok(rgb, box):
                continue
            aligned = align_face_rough(rgb, box)
            # Sharpness metric
            blur = cv2.Laplacian(cv2.cvtColor(aligned, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
            shots.append((blur, aligned, enc, box))
            if len(shots) >= ENROLL_SHOTS:
                break
    if not shots:
        return None
    shots.sort(key=lambda x: x, reverse=True)
    return shots  # best shot

def add_face_button():
    name = name_var.get().strip()
    mobile = mobile_var.get().strip()
    if not name or not mobile:
        messagebox.showerror("Missing Data", "Enter both Name and Mobile.")
        return
    set_status("Capturing best face shot...", WARN)
    best = capture_best_face_shots()
    if not best:
        messagebox.showerror("Quality", "No high-quality face captured. Try more light and look at camera.")
        set_status("Enrollment failed: low quality", ERR)
        return
    blur, aligned, encoding, box = best
    filename = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    bgr_aligned = cv2.cvtColor(aligned, cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(KNOWN_FACE_DIR, filename), bgr_aligned)
    face_data[name] = {"mobile": mobile, "image": filename}
    with open(DATA_FILE, "w") as f:
        json.dump(face_data, f, indent=4)
    # Reload encodings
    load_known_faces()
    set_status(f"{name} enrolled with high-quality shot (sharpness {blur:.1f}).", OK)
    name_var.set("")
    mobile_var.set("")

btn_add = Button(frame, text="Add Face", command=add_face_button)
style_button(btn_add)
btn_add.grid(row=3, column=1, padx=6, pady=8, sticky="w")

# -----------------------
# Recognition loop
# -----------------------
marked_attendance = {}  # name -> last_time
current_frame = None

def log_attendance(name):
    now = datetime.now()
    last = marked_attendance.get(name)
    if last and (now - last).total_seconds() < COOLDOWN_SECS:
        return
    mobile = face_data[name]['mobile']
    with open(ATTENDANCE_FILE, "a", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([name, mobile, now.strftime("%Y-%m-%d %H:%M:%S")])
    marked_attendance[name] = now
    set_status(f"{name} marked present at {now.strftime('%H:%M:%S')}", OK)

def get_frame():
    try:
        resp = urllib.request.urlopen(CAMERA_URL, timeout=2.5)
        img_np = np.frombuffer(resp.read(), dtype=np.uint8)
        return cv2.imdecode(img_np, cv2.IMREAD_COLOR)
    except Exception:
        return None

def recognize_and_draw(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb, number_of_times_to_upsample=UPSCALE, model="hog")
    if not boxes:
        set_status("No face detected.", WARN)
        return frame
    encs = face_recognition.face_encodings(rgb, boxes)

    best_name = None
    best_dist = 1.0
    best_idx = -1
    for idx, (enc, box) in enumerate(zip(encs, boxes)):
        if not face_quality_ok(rgb, box):
            # draw red box for low-quality face
            top, right, bottom, left = box
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.putText(frame, "Low quality", (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
            continue

        # Optional liveness
        if not liveness_pass(rgb, box):
            top, right, bottom, left = box
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 165, 255), 2)
            cv2.putText(frame, "Liveness fail", (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)
            continue

        if known_face_encodings:
            distances = face_recognition.face_distance(known_face_encodings, enc)
            i = int(np.argmin(distances))
            d = float(distances[i])
            # Secondary margin check: ensure gap to median
            sorted_d = np.sort(distances)
            gap = float(sorted_d[14] - sorted_d) if len(sorted_d) > 1 else 1.0
            if d < DIST_THRESHOLD and (gap >= MARGIN):
                name = known_face_names[i]
            else:
                name = "Unknown"
        else:
            name = "Unknown"
            d = 1.0
            i = -1

        top, right, bottom, left = boxes[idx]
        color = (0, 210, 210) if name != "Unknown" else (255, 255, 255)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, top - 20), (right, top), color, cv2.FILLED)
        cv2.putText(frame, name if name != "Unknown" else "Unknown - Press Add Face",
                    (left + 6, top - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (10, 10, 10), 1)

        if name != "Unknown":
            log_attendance(name)
            if d < best_dist:
                best_dist = d
                best_name = name
                best_idx = i

    if best_name:
        set_status(f"Recognized {best_name} (dist {best_dist:.3f})", ACCENT)
    return frame

def update_frame():
    frame = get_frame()
    if frame is None:
        set_status("No camera feed.", ERR)
        root.after(500, update_frame)
        return

    vis = recognize_and_draw(frame)
    img_rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    imgtk = ImageTk.PhotoImage(image=img_pil)
    video_label.imgtk = imgtk
    video_label.configure(image=imgtk)
    root.after(100, update_frame)

root.protocol("WM_DELETE_WINDOW", root.destroy)
update_frame()
root.mainloop()
