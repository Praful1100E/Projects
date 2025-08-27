import warnings
warnings.filterwarnings(
    "ignore",
    message=".pkg_resources is deprecated as an API.",
    category=UserWarning,
    module="face_recognition_models"
)

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
DATA_FILE = "face_data.json"           # { name: {mobile, image, enc:[128]} }
ATTENDANCE_FILE = "attendance_log.csv"

os.makedirs(KNOWN_FACE_DIR, exist_ok=True)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)
if not os.path.exists(ATTENDANCE_FILE):
    with open(ATTENDANCE_FILE, 'w', newline='') as f:
        csv.writer(f).writerow(['Name', 'Mobile', 'Time'])

# ---------------- Theme (Dark + Cyan) ----------------
BG = "#0b0f14"; BG_PANEL = "#101820"; FG = "#e6f1ff"; ACCENT = "#00d1d1"
BTN_BG = "#16212b"; INPUT_BG = "#0f1720"; WARN = "#ffcc00"; OK = "#16c79a"; ERR = "#ff5c5c"

# ---------------- Accuracy and performance ----------------
DIST_THRESHOLD = 0.45
MARGIN = 0.03
MIN_FACE_SIZE = 80
MIN_BLUR_VAR = 120.0
COOLDOWN_SECS = 120
UPSCALE = 0                 # 0 or 1 is usually enough when downscaling
DOWNSCALE = 0.5             # run detection/encoding at 50% size, then map boxes
RECOG_INTERVAL_MS = 250     # compute recognition at most every 250 ms
ENROLL_TIMEOUT_SEC = 8

# ---------------- Helpers: robust embedding conversion ----------------
def as_list128(x):
    """
    Convert a 128-dim embedding to Python list if it's a NumPy array.
    If already a list, return as-is. Never double-call .tolist() on a list.
    """
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x

def as_np128(x):
    """
    Convert stored embedding (list or np.array) to a NumPy array (float32).
    """
    if isinstance(x, np.ndarray):
        return x.astype(np.float32, copy=False)
    return np.array(x, dtype=np.float32)

# ---------------- Data model ----------------
with open(DATA_FILE, "r") as f:
    face_data = json.load(f)

known_face_encodings = []
known_face_names = []

def ensure_embedding_cached():
    """
    Ensure each entry has a cached embedding at face_data[name]['enc'] (list of 128).
    Drops entries with missing/bad images.
    """
    changed = False
    for name in list(face_data.keys()):
        info = face_data[name]
        enc = info.get('enc')
        img_name = info.get('image')
        img_path = os.path.join(KNOWN_FACE_DIR, img_name) if img_name else None

        if enc and isinstance(enc, list) and len(enc) == 128:
            continue  # already cached as list

        if not img_path or not os.path.exists(img_path):
            # Missing image; drop
            face_data.pop(name, None)
            changed = True
            continue

        # Compute enc from image
        img = face_recognition.load_image_file(img_path)
        locs = face_recognition.face_locations(img, number_of_times_to_upsample=0, model="hog")
        encs = face_recognition.face_encodings(img, locs)
        if not encs:
            # No face found; drop entry
            face_data.pop(name, None)
            changed = True
            continue

        face_data[name]['enc'] = as_list128(encs[0])
        changed = True

    if changed:
        with open(DATA_FILE, "w") as f:
            json.dump(face_data, f, indent=2)

def load_known_faces():
    known_face_encodings.clear()
    known_face_names.clear()
    for name, info in face_data.items():
        enc = info.get('enc')
        if enc and len(enc) == 128:
            known_face_encodings.append(as_np128(enc))
            known_face_names.append(name)

ensure_embedding_cached()
load_known_faces()

# ---------------- Camera reader ----------------
class CameraReader:
    def __init__(self, index=0, width=1280, height=720):
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
        backend = cv2.CAP_DSHOW if hasattr(cv2, 'CAP_DSHOW') else 0
        self.cap = cv2.VideoCapture(self.index, backend)
        # Best-effort tuning
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        consecutive_fail = 0
        while self.running:
            if not self.cap:
                time.sleep(0.02)
                continue
            ok, frame = self.cap.read()
            if not ok:
                consecutive_fail += 1
                if consecutive_fail > 30:
                    self._reopen()
                    consecutive_fail = 0
                time.sleep(0.01)
                continue
            consecutive_fail = 0
            with self.frame_lock:
                self.latest_frame = frame
            time.sleep(0.002)

    def _reopen(self):
        try:
            if self.cap:
                self.cap.release()
        except Exception:
            pass
        time.sleep(0.15)
        backend = cv2.CAP_DSHOW if hasattr(cv2, 'CAP_DSHOW') else 0
        self.cap = cv2.VideoCapture(self.index, backend)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

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

camera = CameraReader(index=0)

# ---------------- UI helpers ----------------
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

def map_boxes(scale, boxes):
    if scale == 1.0:
        return boxes
    mapped = []
    inv = 1.0 / scale
    for (t, r, b, l) in boxes:
        mapped.append((int(t*inv), int(r*inv), int(b*inv), int(l*inv)))
    return mapped

# ---------------- Recognition state ----------------
last_recog_ts = 0
overlay_state = {'boxes': [], 'names': [], 'distances': []}
marked_attendance = {}

def draw_overlay(rgb_full, frame_bgr):
    for (box, name, d) in zip(overlay_state['boxes'], overlay_state['names'], overlay_state['distances']):
        t, r, b, l = box
        if name == "LowQ":
            color = (0, 0, 255)
            label = "Low quality"
        else:
            color = (0, 210, 210) if name != "Unknown" else (255, 255, 255)
            label = name if name != "Unknown" else "Unknown - Press Add Face"

        cv2.rectangle(frame_bgr, (l, t), (r, b), color, 2)
        cv2.rectangle(frame_bgr, (l, max(0, t - 20)), (r, t), color, cv2.FILLED)
        cv2.putText(frame_bgr, label, (l + 6, max(12, t - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (10, 10, 10), 1)

        if name not in ("Unknown", "LowQ"):
            set_status(f"Recognized {name}", ACCENT)
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

def recognize_and_draw(frame_bgr):
    global last_recog_ts
    rgb_full = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    now_ms = int(time.time() * 1000)
    need_recog = (now_ms - last_recog_ts) >= RECOG_INTERVAL_MS
    if not need_recog:
        return draw_overlay(rgb_full, frame_bgr)

    # Downscaled detection for speed
    if DOWNSCALE != 1.0:
        small_rgb = cv2.resize(rgb_full, (0, 0), fx=DOWNSCALE, fy=DOWNSCALE)
    else:
        small_rgb = rgb_full

    boxes_small = face_recognition.face_locations(
        small_rgb, number_of_times_to_upsample=UPSCALE, model="hog"
    )
    boxes = map_boxes(DOWNSCALE, boxes_small)
    encs = face_recognition.face_encodings(rgb_full, boxes) if boxes else []

    overlay_state['boxes'] = boxes
    overlay_state['names'] = []
    overlay_state['distances'] = []

    for box, enc in zip(boxes, encs):
        if not face_quality_ok(rgb_full, box):
            overlay_state['names'].append("LowQ")
            overlay_state['distances'].append(1.0)
            continue

        name = "Unknown"; d = 1.0
        if known_face_encodings:
            distances = face_recognition.face_distance(known_face_encodings, enc)
            i = int(np.argmin(distances))
            d = float(distances[i])
            s = np.sort(distances)
            gap = float(s[1]-s[0]) if len(s) > 1 else 1.0
            if d < DIST_THRESHOLD and gap >= MARGIN:
                name = known_face_names[i]

        overlay_state['names'].append(name)
        overlay_state['distances'].append(d)
        if name != "Unknown":
            log_attendance(name)

    last_recog_ts = now_ms
    return draw_overlay(rgb_full, frame_bgr)

def capture_best_enroll_shot(timeout_sec=ENROLL_TIMEOUT_SEC):
    best = None
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        frame = camera.read()
        if frame is None:
            time.sleep(0.02)
            continue
        rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        small = cv2.resize(rgb_full, (0, 0), fx=DOWNSCALE, fy=DOWNSCALE)
        boxes_small = face_recognition.face_locations(small, number_of_times_to_upsample=UPSCALE, model="hog")
        boxes = map_boxes(DOWNSCALE, boxes_small)
        encs = face_recognition.face_encodings(rgb_full, boxes)
        for box, enc in zip(boxes, encs):
            if not face_quality_ok(rgb_full, box):
                continue
            t, r, b, l = box
            crop = rgb_full[t:b, l:r]
            blur = cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
            if (best is None) or (blur > best[0]):
                best = (blur, crop, enc)
            if best and best[0] > MIN_BLUR_VAR * 2 and (b - t) > int(MIN_FACE_SIZE * 1.2):
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
lbl_cam = Label(top_frame, text="Camera Index:"); style_label(lbl_cam); lbl_cam.grid(row=0, column=0, padx=6, pady=6, sticky="w")
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

btn_start = Button(top_frame, text="Start Camera", command=start_camera); style_button(btn_start); btn_start.grid(row=0, column=2, padx=6, pady=6)
btn_stop = Button(top_frame, text="Stop Camera", command=stop_camera); style_button(btn_stop); btn_stop.grid(row=0, column=3, padx=6, pady=6)

# Name/Mobile
lbl_name = Label(top_frame, text="Name:"); style_label(lbl_name); lbl_name.grid(row=1, column=0, padx=6, pady=6, sticky="w")
name_var = StringVar()
ent_name = Entry(top_frame, textvariable=name_var, width=30); style_entry(ent_name); ent_name.grid(row=1, column=1, padx=6, pady=6, sticky="w")

lbl_mobile = Label(top_frame, text="Mobile:"); style_label(lbl_mobile); lbl_mobile.grid(row=2, column=0, padx=6, pady=6, sticky="w")
mobile_var = StringVar()
ent_mobile = Entry(top_frame, textvariable=mobile_var, width=30); style_entry(ent_mobile); ent_mobile.grid(row=2, column=1, padx=6, pady=6, sticky="w")

# Add face button
def add_face_button():
    if not camera.running:
        messagebox.showerror("Camera", "Start the camera first."); return
    name = name_var.get().strip()
    mobile = mobile_var.get().strip()
    if not name or not mobile:
        messagebox.showerror("Missing Data", "Enter both Name and Mobile."); return
    set_status("Capturing best face shot...", WARN)
    best = capture_best_enroll_shot()
    if not best:
        messagebox.showerror("Quality", "No high-quality face captured. Improve lighting and try again.")
        set_status("Enrollment failed: low quality", ERR); return
    blur, crop_rgb, enc = best
    filename = f"{name}_{int(time.time())}.jpg"
    cv2.imwrite(os.path.join(KNOWN_FACE_DIR, filename), cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR))
    # Update data model with cached embedding (SAFE: only tolist if array)
    face_data[name] = {"mobile": mobile, "image": filename, "enc": as_list128(enc)}
    with open(DATA_FILE, "w") as f:
        json.dump(face_data, f, indent=2)
    load_known_faces()
    set_status(f"{name} enrolled (sharpness {blur:.1f}).", OK)
    name_var.set(""); mobile_var.set("")

btn_add = Button(top_frame, text="Add Face", command=add_face_button); style_button(btn_add); btn_add.grid(row=3, column=1, padx=6, pady=8, sticky="w")

# Status
status_var = StringVar()
status_label = Label(root, textvariable=status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 12, "bold"))
status_label.pack(pady=6)

# Video panel
video_frame = Frame(root, bg=BG_PANEL, bd=0, highlightthickness=1, highlightbackground=ACCENT)
video_frame.pack(padx=10, pady=10)
video_label = Label(video_frame, bg=BG_PANEL)
video_label.pack()

def update_frame():
    if not camera.running:
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
    root.after(40, update_frame)

def on_close():
    try: camera.stop()
    except Exception: pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
set_status("Click 'Start Camera' to begin.", ACCENT)
update_frame()
root.mainloop()
