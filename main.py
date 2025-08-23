import csv
import os
import random
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formataddr

from flask import Flask, render_template_string, request, redirect, url_for, flash, send_file
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "dev-secret-key")

# -----------------------------
# Config
# -----------------------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
BLACKBOX_FILE = os.path.join(LOG_DIR, "blackbox_log.csv")

MAIL_ENABLED = os.environ.get("MAIL_ENABLED", "false").lower() == "true"
MAIL_HOST = os.environ.get("MAIL_HOST", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
MAIL_USER = os.environ.get("MAIL_USER", "")
MAIL_PASS = os.environ.get("MAIL_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM", MAIL_USER)
MAIL_TO = os.environ.get("MAIL_TO", "")

# -----------------------------
# Helpers: Email
# -----------------------------
class MailSender:
    def __init__(self, host, port, user, password, sender, to_addr, enabled=False):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.to_addr = to_addr
        self.enabled = enabled

    def send(self, subject, body):
        if not self.enabled:
            return False, "Mail disabled (enable by setting MAIL_ENABLED=true)"
        if not (self.user and self.password and self.sender and self.to_addr):
            return False, "Mail credentials not configured"
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = formataddr(("Smart RC Car", self.sender))
            msg["To"] = self.to_addr

            context = ssl.create_default_context()
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls(context=context)
                server.login(self.user, self.password)
                server.sendmail(self.sender, [self.to_addr], msg.as_string())
            return True, "Email sent"
        except Exception as e:
            return False, f"Email error: {e}"

mailer = MailSender(
    MAIL_HOST, MAIL_PORT, MAIL_USER, MAIL_PASS, MAIL_FROM, MAIL_TO, MAIL_ENABLED
)

# -----------------------------
# Persistence: CSV Header
# -----------------------------
CSV_HEADER = [
    "timestamp_iso",
    "speed_kmh",
    "accel_g",
    "impact_g",
    "gps_lat",
    "gps_lng",
    "ultra_front_cm",
    "ultra_left_cm",
    "ultra_right_cm",
    "ir_left",
    "ir_center",
    "ir_right",
    "voice_cmd",
    "auto_brake_engaged",
    "blindspot_left",
    "blindspot_right",
    "collision_detected",
    "emergency_alert_sent"
]

if not os.path.exists(BLACKBOX_FILE):
    with open(BLACKBOX_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)

# -----------------------------
# State (simulated)
# -----------------------------
state = {
    "speed_kmh": 0.0,
    "accel_g": 0.0,
    "impact_g": 0.0,
    "gps_lat": 31.7310,   # Shimla-ish default; user is in Himachal
    "gps_lng": 76.9850,
    "ultra_front_cm": 120.0,
    "ultra_left_cm": 150.0,
    "ultra_right_cm": 150.0,
    "ir_left": 0,     # 0 = not detecting line, 1 = detecting
    "ir_center": 0,
    "ir_right": 0,
    "voice_cmd": "",
    "auto_brake_engaged": False,
    "blindspot_left": False,
    "blindspot_right": False,
    "collision_detected": False,
    "emergency_alert_sent": False,
}

# -----------------------------
# Control Logic Parameters
# -----------------------------
BLINDSPOT_THRESHOLD_CM = 70.0
COLLISION_THRESHOLD_CM = 25.0
IMPACT_ALERT_THRESHOLD_G = 2.5

# -----------------------------
# Logic
# -----------------------------
def compute_blindspots(left_cm, right_cm):
    left = left_cm <= BLINDSPOT_THRESHOLD_CM
    right = right_cm <= BLINDSPOT_THRESHOLD_CM
    return left, right

def compute_collision(front_cm):
    return front_cm <= COLLISION_THRESHOLD_CM

def apply_voice_command(cmd, current_speed):
    cmd = (cmd or "").strip().lower()
    speed = current_speed
    if cmd in ["forward", "go", "move", "resume"]:
        speed = max(10.0, current_speed)  # ensure some movement
    elif cmd in ["stop", "halt", "brake"]:
        speed = 0.0
    elif cmd in ["left", "turn left"]:
        # Here just annotate; real implementation would steer via motor driver
        pass
    elif cmd in ["right", "turn right"]:
        pass
    return speed

def maybe_emergency_email(impact_g, collision, lat, lng):
    if impact_g >= IMPACT_ALERT_THRESHOLD_G or collision:
        subject = "Smart RC Car: Crash/Collision Alert"
        body = f"Potential crash detected.\nImpact(g): {impact_g}\nCollision: {collision}\nGPS: {lat}, {lng}\nTime: {datetime.utcnow().isoformat()}Z"
        ok, msg = mailer.send(subject, body)
        return ok, msg
    return False, "No alert criteria met"

def append_blackbox_row():
    row = [
        datetime.utcnow().isoformat() + "Z",
        state["speed_kmh"],
        state["accel_g"],
        state["impact_g"],
        state["gps_lat"],
        state["gps_lng"],
        state["ultra_front_cm"],
        state["ultra_left_cm"],
        state["ultra_right_cm"],
        state["ir_left"],
        state["ir_center"],
        state["ir_right"],
        state["voice_cmd"],
        state["auto_brake_engaged"],
        state["blindspot_left"],
        state["blindspot_right"],
        state["collision_detected"],
        state["emergency_alert_sent"],
    ]
    with open(BLACKBOX_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

# -----------------------------
# UI Template (Dark + Cyan)
# -----------------------------
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Smart RC Car Dashboard</title>
  <style>
    :root {
      --bg: #0b0f13;
      --panel: #121820;
      --card: #0f141a;
      --text: #e6f1ff;
      --muted: #9fb3c8;
      --cyan: #00d1d1;
      --accent: #18ffff;
      --danger: #ff4d4d;
      --ok: #49d36d;
      --warn: #ffb020;
      --border: #1f2a36;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; padding: 0; background: var(--bg); color: var(--text);
      font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
    }
    header {
      background: linear-gradient(90deg, #0b0f13, #101821);
      border-bottom: 1px solid var(--border);
      padding: 16px 24px;
      display: flex; align-items: center; justify-content: space-between;
    }
    h1 { margin: 0; font-weight: 700; letter-spacing: 0.3px; }
    .accent { color: var(--cyan); }
    main { padding: 20px; max-width: 1200px; margin: 0 auto; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 0 0 transparent;
    }
    .card h2 {
      margin: 0 0 12px 0; font-size: 18px; color: var(--accent);
      font-weight: 600;
    }
    label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
    input, select {
      width: 100%;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--text);
      outline: none;
    }
    input:focus { border-color: var(--cyan); }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .btn {
      display: inline-block; padding: 10px 14px; border-radius: 8px;
      border: 1px solid var(--border); color: var(--text); background: #0e151c;
      cursor: pointer; text-decoration: none; font-weight: 600;
    }
    .btn:hover { border-color: var(--cyan); }
    .btn-primary { background: #072125; border-color: #0b3a3f; color: var(--accent); }
    .btn-danger { background: #2a1214; border-color: #4d2023; color: var(--danger); }
    .btn-ok { background: #112717; border-color: #1f4627; color: var(--ok); }
    .tag { display: inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); font-size: 12px; }
    .tag-ok { color: var(--ok); border-color: #1f4627; background: #0b1a10; }
    .tag-warn { color: var(--warn); border-color: #5c4413; background: #1a1408; }
    .tag-danger { color: var(--danger); border-color: #4d2023; background: #1a0c0d; }
    .muted { color: var(--muted); }
    footer { padding: 20px; color: var(--muted); text-align: center; }
    .flash { padding: 10px 12px; border-radius: 8px; margin-bottom: 12px; border: 1px solid var(--border); }
    .flash-ok { color: var(--ok); background: #0b1a10; border-color: #1f4627; }
    .flash-warn { color: var(--warn); background: #1a1408; border-color: #5c4413; }
    .flash-danger { color: var(--danger); background: #1a0c0d; border-color: #4d2023; }
    .toolbar { display:flex; gap:10px; flex-wrap: wrap; }
    a.download { color: var(--cyan); text-decoration: none; }
  </style>
</head>
<body>
  <header>
    <h1>Smart RC Car <span class="accent">Dashboard</span></h1>
    <div class="muted">Dark + Cyan • Manual Simulation</div>
  </header>
  <main>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="flash {% if category=='ok' %}flash-ok{% elif category=='warn' %}flash-warn{% else %}flash-danger{% endif %}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="grid">
      <div class="card">
        <h2>Manual Inputs</h2>
        <form method="post" action="{{ url_for('update') }}">
          <div class="row">
            <div>
              <label>Speed (km/h)</label>
              <input type="number" step="0.1" name="speed_kmh" value="{{ s.speed_kmh }}">
            </div>
            <div>
              <label>Accel (g)</label>
              <input type="number" step="0.1" name="accel_g" value="{{ s.accel_g }}">
            </div>
          </div>
          <div class="row">
            <div>
              <label>Impact (g)</label>
              <input type="number" step="0.1" name="impact_g" value="{{ s.impact_g }}">
            </div>
            <div>
              <label>Front Ultrasonic (cm)</label>
              <input type="number" step="0.1" name="ultra_front_cm" value="{{ s.ultra_front_cm }}">
            </div>
          </div>
          <div class="row">
            <div>
              <label>Left Ultrasonic (cm)</label>
              <input type="number" step="0.1" name="ultra_left_cm" value="{{ s.ultra_left_cm }}">
            </div>
            <div>
              <label>Right Ultrasonic (cm)</label>
              <input type="number" step="0.1" name="ultra_right_cm" value="{{ s.ultra_right_cm }}">
            </div>
          </div>
          <div class="row">
            <div>
              <label>GPS Latitude</label>
              <input type="number" step="0.000001" name="gps_lat" value="{{ s.gps_lat }}">
            </div>
            <div>
              <label>GPS Longitude</label>
              <input type="number" step="0.000001" name="gps_lng" value="{{ s.gps_lng }}">
            </div>
          </div>
          <div class="row">
            <div>
              <label>IR Left (0/1)</label>
              <input type="number" min="0" max="1" name="ir_left" value="{{ s.ir_left }}">
            </div>
            <div>
              <label>IR Center (0/1)</label>
              <input type="number" min="0" max="1" name="ir_center" value="{{ s.ir_center }}">
            </div>
          </div>
          <div class="row">
            <div>
              <label>IR Right (0/1)</label>
              <input type="number" min="0" max="1" name="ir_right" value="{{ s.ir_right }}">
            </div>
            <div>
              <label>Voice Command (forward/stop/left/right)</label>
              <input type="text" name="voice_cmd" value="{{ s.voice_cmd }}">
            </div>
          </div>

          <div class="toolbar" style="margin-top:12px;">
            <button class="btn btn-primary" type="submit">Update & Log</button>
            <a class="btn" href="{{ url_for('randomize') }}">Randomize</a>
            <a class="btn" href="{{ url_for('download_log') }}">Download Log CSV</a>
          </div>
        </form>
      </div>

      <div class="card">
        <h2>Status & Alerts</h2>
        <p><strong>Speed:</strong> {{ "%.1f"|format(s.speed_kmh) }} km/h</p>
        <p><strong>Front Distance:</strong> {{ "%.1f"|format(s.ultra_front_cm) }} cm</p>
        <p><strong>Blind Spots:</strong>
          {% if s.blindspot_left %}<span class="tag tag-warn">Left</span>{% else %}<span class="tag tag-ok">Left Clear</span>{% endif %}
          {% if s.blindspot_right %}<span class="tag tag-warn">Right</span>{% else %}<span class="tag tag-ok">Right Clear</span>{% endif %}
        </p>
        <p><strong>Collision:</strong>
          {% if s.collision_detected %}<span class="tag tag-danger">Detected</span>{% else %}<span class="tag tag-ok">No</span>{% endif %}
        </p>
        <p><strong>Auto Brake:</strong>
          {% if s.auto_brake_engaged %}<span class="tag tag-warn">Engaged</span>{% else %}<span class="tag tag-ok">Off</span>{% endif %}
        </p>
        <p><strong>Lane Tracking:</strong>
          {% if s.ir_left==1 or s.ir_center==1 or s.ir_right==1 %}
            <span class="tag">Line Detected</span>
          {% else %}
            <span class="tag">No Line</span>
          {% endif %}
        </p>
        <p><strong>Impact(g):</strong> {{ "%.1f"|format(s.impact_g) }}
          {% if s.impact_g >= 2.5 %}
            <span class="tag tag-danger">High</span>
          {% else %}
            <span class="tag tag-ok">Normal</span>
          {% endif %}
        </p>
        <p class="muted">GPS: {{ "%.6f"|format(s.gps_lat) }}, {{ "%.6f"|format(s.gps_lng) }}</p>
      </div>

      <div class="card">
        <h2>System Controls</h2>
        <form method="post" action="{{ url_for('send_test_email') }}">
          <p class="muted">Emergency alert uses email as placeholder for SMS. Configure .env for SMTP.</p>
          <div class="toolbar">
            <button class="btn btn-ok" type="submit">Send Test Alert</button>
            {% if mail_enabled %}
              <span class="tag tag-ok">Mail Enabled</span>
            {% else %}
              <span class="tag tag-warn">Mail Disabled</span>
            {% endif %}
          </div>
        </form>
        <div style="margin-top:12px;">
          <p><strong>Thresholds</strong></p>
          <p class="muted">Blindspot ≤ {{ blind }} cm • Collision ≤ {{ coll }} cm • Impact ≥ {{ impact }} g</p>
        </div>
      </div>
    </div>

  </main>
  <footer>
    Smart RC Car • Flask • CSV Black Box • Voice Command (sim) • Dark + Cyan Theme
  </footer>
</body>
</html>
"""

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    return render_template_string(
        TEMPLATE,
        s=state,
        mail_enabled=MAIL_ENABLED,
        blind=BLINDSPOT_THRESHOLD_CM,
        coll=COLLISION_THRESHOLD_CM,
        impact=IMPACT_ALERT_THRESHOLD_G
    )

@app.route("/update", methods=["POST"])
def update():
    try:
        # Parse inputs
        speed_kmh = float(request.form.get("speed_kmh", state["speed_kmh"]))
        accel_g = float(request.form.get("accel_g", state["accel_g"]))
        impact_g = float(request.form.get("impact_g", state["impact_g"]))
        ultra_front_cm = float(request.form.get("ultra_front_cm", state["ultra_front_cm"]))
        ultra_left_cm = float(request.form.get("ultra_left_cm", state["ultra_left_cm"]))
        ultra_right_cm = float(request.form.get("ultra_right_cm", state["ultra_right_cm"]))
        gps_lat = float(request.form.get("gps_lat", state["gps_lat"]))
        gps_lng = float(request.form.get("gps_lng", state["gps_lng"]))
        ir_left = int(request.form.get("ir_left", state["ir_left"]))
        ir_center = int(request.form.get("ir_center", state["ir_center"]))
        ir_right = int(request.form.get("ir_right", state["ir_right"]))
        voice_cmd = request.form.get("voice_cmd", "").strip()

        # Apply voice command to speed
        speed_kmh = apply_voice_command(voice_cmd, speed_kmh)

        # Compute logic
        blind_left, blind_right = compute_blindspots(ultra_left_cm, ultra_right_cm)
        collision = compute_collision(ultra_front_cm)

        auto_brake_engaged = False
        if collision:
            speed_kmh = 0.0
            auto_brake_engaged = True

        # Update state
        state.update({
            "speed_kmh": speed_kmh,
            "accel_g": accel_g,
            "impact_g": impact_g,
            "gps_lat": gps_lat,
            "gps_lng": gps_lng,
            "ultra_front_cm": ultra_front_cm,
            "ultra_left_cm": ultra_left_cm,
            "ultra_right_cm": ultra_right_cm,
            "ir_left": 1 if ir_left else 0,
            "ir_center": 1 if ir_center else 0,
            "ir_right": 1 if ir_right else 0,
            "voice_cmd": voice_cmd,
            "auto_brake_engaged": auto_brake_engaged,
            "blindspot_left": blind_left,
            "blindspot_right": blind_right,
            "collision_detected": collision,
        })

        # Emergency alert if needed
        alert_sent = False
        if impact_g >= IMPACT_ALERT_THRESHOLD_G or collision:
            ok, msg = maybe_emergency_email(impact_g, collision, gps_lat, gps_lng)
            alert_sent = ok
            if ok:
                flash("Emergency alert sent", "ok")
            else:
                # Only warn; email may be disabled intentionally
                flash(f"Emergency alert not sent: {msg}", "warn")

        state["emergency_alert_sent"] = alert_sent

        # Append Black Box Log
        append_blackbox_row()

        flash("State updated & logged", "ok")
    except Exception as e:
        flash(f"Error: {e}", "err")
    return redirect(url_for("index"))

@app.route("/randomize")
def randomize():
    # Quick random simulation
    state["speed_kmh"] = round(random.uniform(0, 40), 1)
    state["accel_g"] = round(random.uniform(0, 1.2), 2)
    state["impact_g"] = round(random.choice([0.0, 0.3, 0.5, 2.6, 3.1]), 2)
    state["ultra_front_cm"] = round(random.uniform(10, 200), 1)
    state["ultra_left_cm"] = round(random.uniform(20, 200), 1)
    state["ultra_right_cm"] = round(random.uniform(20, 200), 1)
    state["gps_lat"] += round(random.uniform(-0.0005, 0.0005), 6)
    state["gps_lng"] += round(random.uniform(-0.0005, 0.0005), 6)
    state["ir_left"] = random.choice([0, 1])
    state["ir_center"] = random.choice([0, 1])
    state["ir_right"] = random.choice([0, 1])
    state["voice_cmd"] = random.choice(["", "forward", "stop", "left", "right"])

    # Recompute logic
    state["blindspot_left"], state["blindspot_right"] = compute_blindspots(
        state["ultra_left_cm"], state["ultra_right_cm"]
    )
    state["collision_detected"] = compute_collision(state["ultra_front_cm"])
    state["auto_brake_engaged"] = False
    if state["collision_detected"]:
        state["speed_kmh"] = 0.0
        state["auto_brake_engaged"] = True

    # Log
    append_blackbox_row()
    flash("Randomized values & logged", "ok")
    return redirect(url_for("index"))

@app.route("/download")
def download_log():
    return send_file(BLACKBOX_FILE, as_attachment=True)

@app.route("/send-test-email", methods=["POST"])
def send_test_email():
    ok, msg = mailer.send("Smart RC Car: Test Alert", "This is a test alert from Flask dashboard.")
    if ok:
        flash("Test email sent", "ok")
    else:
        flash(f"Test email failed: {msg}", "warn")
    return redirect(url_for("index"))

# -----------------------------
# Entry
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
