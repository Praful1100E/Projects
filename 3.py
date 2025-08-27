import warnings
warnings.filterwarnings(
    "ignore",
    message=".pkg_resources is deprecated as an API.",
    category=UserWarning,
    module="face_recognition_models"
)
import face_recognition
import cv2
import os
import json
import csv
from datetime import datetime

# -----------------------------
# File paths
# -----------------------------
DATA_FILE = "face_data.json"
ATTENDANCE_FILE = "attendance_log.csv"
PHOTO_PATH = "pproject/shivani_20250730135307.jpg"  # Yaha apni photo ka full path ya file name daalo

# -----------------------------
# Step 1: Ensure files exist
# -----------------------------
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)  # Empty JSON

if not os.path.exists(ATTENDANCE_FILE):
    with open(ATTENDANCE_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Date", "Time"])  # CSV header

# -----------------------------
# Step 2: Load photo and encode
# -----------------------------
image = face_recognition.load_image_file(PHOTO_PATH)
face_locations = face_recognition.face_locations(image)
face_encodings = face_recognition.face_encodings(image, face_locations)

print(f"Number of faces detected in photo: {len(face_locations)}")

if len(face_encodings) == 0:
    print("No face found in the image. Check your photo.")
else:
    # Load existing face data
    with open(DATA_FILE, 'r') as f:
        face_data = json.load(f)

    # For simplicity, assume only one face in the image
    name = "Isha"  # Tum apna naam change kar sakti ho
    face_data[name] = face_encodings[0].tolist()  # Convert numpy array to list

    # Save updated face data
    with open(DATA_FILE, 'w') as f:
        json.dump(face_data, f)

    # -----------------------------
    # Step 3: Record attendance
    # -----------------------------
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    with open(ATTENDANCE_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([name, date_str, time_str])

    print(f"Attendance recorded for {name} on {date_str} at {time_str}")
import cv2
import face_recognition
import numpy as np
import os
import json
import csv
import threading
import time
from datetime import datetime
from tkinter import Tk, Label, Entry, Button, StringVar, Frame, messagebox, OptionMenu
from PIL import Image, ImageTk

# ---------------- Paths & files ----------------
KNOWN_FACE_DIR = "known_faces"
DATA_FILE = "face_data.json"
ATTENDANCE_FILE = "attendance_log.csv"

os.makedirs(KNOWN_FACE_DIR, exist_ok=True)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)
if not os.path.exists(ATTENDANCE_FILE):
    with open(ATTENDANCE_FILE, 'w', newline='') as f:
        csv.writer(f).writerow(['Name', 'Mobile', 'Time'])

# ---------------- Theme (Dark + Cyan) ----------------
BG = "#0b0f14"
BG_PANEL = "#101820"
FG = "#e6f1ff"
ACCENT = "#00d1d1"
BTN_BG = "#16212b"
INPUT_BG = "#0f1720"
WARN = "#ffcc00"
OK = "#16c79a"
ERR = "#ff5c5c"

# ---------------- Accuracy settings ----------------
DIST_THRESHOLD = 0.45      # tighter than default ~0.6
MARGIN = 0.03              # gap to next-best candidate
MIN_FACE_SIZE = 80         # min px for width/height
MIN_BLUR_VAR = 120.0       # Laplacian variance threshold
COOLDOWN_SECS = 120        # per-person cooldown
ENROLL_SHOTS = 5           # take best of N shots for enrollment
UPSCALE = 1                # 0/1/2; higher = more detection cost

# ---------------- Load known faces ----------------
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
        if not os.path.exists(img_path):
            continue
        image = face_recognition.load_image_file(img_path)
        encs = face_recognition.face_encodings(image)
        if encs:
            known_face_encodings.append(encs[0])
            known_face_names.append(name)

load_known_faces()

# ---------------- Camera reader (laptop webcam) ----------------
class CameraReader:
    def _init_(self, index=0, width=1280, height=720):
        self.index = index
        self.width = width
        self.height = height
        self.cap = None
        self.running = False
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.thread = None

    def start(self):
        self.stop()
        self.cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW if hasattr(cv2, 'CAP_DSHOW') else 0)
        # Set resolution if supported
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        except Exception:
            pass
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        consecutive_fail = 0
        while self.running:
            if not self.cap:
                time.sleep(0.05)
                continue
            ok, frame = self.cap.read()
            if not ok:
                consecutive_fail += 1
                if consecutive_fail > 30:
                    # attempt re-open
                    self._reopen()
                    consecutive_fail = 0
                time.sleep(0.01)
                continue
            consecutive_fail = 0
            with self.frame_lock:
                self.latest_frame = frame
            time.sleep(0.005)

    def _reopen(self):
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass
        time.sleep(0.2)
        self.cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW if hasattr(cv2, 'CAP_DSHOW') else 0)
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        except Exception:
            pass

    def read(self):
        with self.frame_lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
        self.thread = None
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass
        self.cap = None

# Global camera instance
camera = CameraReader(index=0)

# ---------------- Helpers ----------------
def set_status(text, color=ACCENT):
    status_var.set(text)
    status_label.configure(fg=color)

def face_quality_ok(rgb_frame, box):
    top, right, bottom, left = box
    w, h = right - left, bottom - top
    if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
        return False
    crop = rgb_frame[top:bottom, left:right]
    if crop.size == 0:
        return False
    blur = cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
    return blur >= MIN_BLUR_VAR

def recognize_and_draw(frame_bgr):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb, number_of_times_to_upsample=UPSCALE, model="hog")
    if not boxes:
        set_status("No face detected.", WARN)
        return frame_bgr
    encs = face_recognition.face_encodings(rgb, boxes)

    best_name, best_dist = None, 1.0
    for box, enc in zip(boxes, encs):
        if not face_quality_ok(rgb, box):
            top, right, bottom, left = box
            cv2.rectangle(frame_bgr, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.putText(frame_bgr, "Low quality", (left, top - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
            continue

        name = "Unknown"
        d = 1.0
        if known_face_encodings:
            distances = face_recognition.face_distance(known_face_encodings, enc)
            i = int(np.argmin(distances))
            d = float(distances[i])
            s = np.sort(distances)
            gap = float(s[1]-s[0]) if len(s) > 1 else 1.0
            if d < DIST_THRESHOLD and gap >= MARGIN:
                name = known_face_names[i]

        top, right, bottom, left = box
        color = (0, 210, 210) if name != "Unknown" else (255, 255, 255)
        cv2.rectangle(frame_bgr, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame_bgr, (left, top - 20), (right, top), color, cv2.FILLED)
        cv2.putText(frame_bgr, name if name != "Unknown" else "Unknown - Press Add Face",
                    (left + 6, top - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (10, 10, 10), 1)

        if name != "Unknown":
            log_attendance(name)
            if d < best_dist:
                best_dist = d
                best_name = name

    if best_name:
        set_status(f"Recognized {best_name} (dist {best_dist:.3f})", ACCENT)
    return frame_bgr

def log_attendance(name):
    now = datetime.now()
    last = marked_attendance.get(name)
    if last and (now - last).total_seconds() < COOLDOWN_SECS:
        return
    mobile = face_data[name]['mobile']
    with open(ATTENDANCE_FILE, "a", newline='') as f:
        csv.writer(f).writerow([name, mobile, now.strftime("%Y-%m-%d %H:%M:%S")])
    marked_attendance[name] = now
    set_status(f"{name} marked present at {now.strftime('%H:%M:%S')}", OK)

def capture_best_enroll_shot(timeout_sec=8):
    best = None
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        frame = camera.read()
        if frame is None:
            time.sleep(0.02)
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb, number_of_times_to_upsample=UPSCALE, model="hog")
        encs = face_recognition.face_encodings(rgb, boxes)
        for box, enc in zip(boxes, encs):
            if not face_quality_ok(rgb, box):
                continue
            crop = rgb[box[0]:box[2], box[3]:box[1]]
            blur = cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
            if (best is None) or (blur > best[0]):
                best = (blur, crop, enc)
            if best and best[0] > MIN_BLUR_VAR * 2 and (box[2]-box[0]) > MIN_FACE_SIZE*1.2:
                return best
    return best

# ---------------- Tkinter UI ----------------
root = Tk()
root.title("Face Attendance (Laptop Camera)")
root.configure(bg=BG)

def style_label(w): w.configure(bg=BG_PANEL, fg=FG)
def style_entry(w): w.configure(bg=INPUT_BG, fg=FG, insertbackground=FG, highlightthickness=1, highlightbackground=ACCENT)
def style_button(w): w.configure(bg=BTN_BG, fg=FG, activebackground=ACCENT, activeforeground="#001015", bd=0, highlightthickness=1, highlightbackground=ACCENT)

top_frame = Frame(root, bg=BG_PANEL, bd=0, highlightthickness=1, highlightbackground=ACCENT)
top_frame.pack(padx=10, pady=10, fill="x")

# Camera controls
camera_index_var = StringVar(value="0")
lbl_cam = Label(top_frame, text="Camera Index:")
style_label(lbl_cam); lbl_cam.grid(row=0, column=0, padx=6, pady=6, sticky="w")
cam_menu = OptionMenu(top_frame, camera_index_var, "0", "1", "2", "3")
cam_menu.configure(bg=BTN_BG, fg=FG, highlightthickness=1, highlightbackground=ACCENT, activebackground=ACCENT, activeforeground="#001015")
cam_menu.grid(row=0, column=1, padx=6, pady=6, sticky="w")

def start_camera():
    try:
        idx = int(camera_index_var.get())
    except Exception:
        idx = 0
    camera.index = idx
    camera.start()
    set_status(f"Camera started (index {idx})", OK)

def stop_camera():
    camera.stop()
    set_status("Camera stopped", WARN)

btn_start = Button(top_frame, text="Start Camera", command=start_camera)
style_button(btn_start); btn_start.grid(row=0, column=2, padx=6, pady=6)
btn_stop = Button(top_frame, text="Stop Camera", command=stop_camera)
style_button(btn_stop); btn_stop.grid(row=0, column=3, padx=6, pady=6)

# Name/Mobile
lbl_name = Label(top_frame, text="Name:")
style_label(lbl_name); lbl_name.grid(row=1, column=0, padx=6, pady=6, sticky="w")
name_var = StringVar()
ent_name = Entry(top_frame, textvariable=name_var, width=30)
style_entry(ent_name); ent_name.grid(row=1, column=1, padx=6, pady=6, sticky="w")

lbl_mobile = Label(top_frame, text="Mobile:")
style_label(lbl_mobile); lbl_mobile.grid(row=2, column=0, padx=6, pady=6, sticky="w")
mobile_var = StringVar()
ent_mobile = Entry(top_frame, textvariable=mobile_var, width=30)
style_entry(ent_mobile); ent_mobile.grid(row=2, column=1, padx=6, pady=6, sticky="w")

# Add face button
def add_face_button():
    if not camera.running:
        messagebox.showerror("Camera", "Start the camera first.")
        return
    name = name_var.get().strip()
    mobile = mobile_var.get().strip()
    if not name or not mobile:
        messagebox.showerror("Missing Data", "Enter both Name and Mobile.")
        return
    set_status("Capturing best face shot...", WARN)
    best = capture_best_enroll_shot()
    if not best:
        messagebox.showerror("Quality", "No high-quality face captured. Improve lighting and try again.")
        set_status("Enrollment failed: low quality", ERR)
        return
    blur, crop_rgb, enc = best
    filename = f"{name}_{int(time.time())}.jpg"
    cv2.imwrite(os.path.join(KNOWN_FACE_DIR, filename), cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR))
    # Update data and encodings
    face_data[name] = {"mobile": mobile, "image": filename}
    with open(DATA_FILE, "w") as f:
        json.dump(face_data, f, indent=2)
    load_known_faces()
    set_status(f"{name} enrolled (sharpness {blur:.1f}).", OK)
    name_var.set(""); mobile_var.set("")

btn_add = Button(top_frame, text="Add Face", command=add_face_button)
style_button(btn_add); btn_add.grid(row=3, column=1, padx=6, pady=8, sticky="w")

# Status
status_var = StringVar()
status_label = Label(root, textvariable=status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 12, "bold"))
status_label.pack(pady=6)

# Video panel
video_frame = Frame(root, bg=BG_PANEL, bd=0, highlightthickness=1, highlightbackground=ACCENT)
video_frame.pack(padx=10, pady=10)
video_label = Label(video_frame, bg=BG_PANEL)
video_label.pack()

# Recognition loop state
marked_attendance = {}

def update_frame():
    if not camera.running:
        # show idle message
        blank = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Camera stopped. Click 'Start Camera'.", (20, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
        img_rgb = cv2.cvtColor(blank, cv2.COLOR_BGR2RGB)
    else:
        frame = camera.read()
        if frame is None:
            set_status("Waiting for camera frames...", WARN)
            img_rgb = np.zeros((360, 640, 3), dtype=np.uint8)
        else:
            vis = recognize_and_draw(frame)
            img_rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)

    img_pil = Image.fromarray(img_rgb)
    imgtk = ImageTk.PhotoImage(image=img_pil)
    video_label.imgtk = imgtk
    video_label.configure(image=imgtk)
    root.after(120, update_frame)

def on_close():
    try:
        camera.stop()
    except Exception:
        pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
set_status("Click 'Start Camera' to begin.", ACCENT)
update_frame()
root.mainloop()