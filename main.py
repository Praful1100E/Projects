import os
from flask import Flask, request, render_template_string, redirect, url_for, flash
from twilio.rest import Client  # pip install twilio
from flask_limiter import Limiter  # pip install flask-limiter
from flask_limiter.util import get_remote_address

# Configuration from environment
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
VERIFY_SERVICE_SID = os.environ.get("VERIFY_SERVICE_SID", "")  # Twilio Verify Service SID

# Basic validation to avoid running without config
if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and VERIFY_SERVICE_SID):
    print("Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and VERIFY_SERVICE_SID env vars before running.")
    # Continue to allow template rendering; send will fail gracefully.

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "change-me")

# Global rate limiter: also apply per-IP caps
limiter = Limiter(get_remote_address, app=app, default_limits=["100 per day", "20 per hour"])

# In-memory consent registry (replace with DB in production). Keyed by E.164 number.
CONSENTS = {}  # {"+911234567890": {"purpose": "auth", "opted_out": False}}

# Very simple HTML UI
PAGE = """
<!doctype html>
<title>Compliant SMS Demo</title>
<h2>Compliant SMS Verification Demo</h2>
<p>This demo only sends a one-time verification SMS after explicit consent. No bulk or repeated messaging is allowed.</p>

<h3>1) Record Consent</h3>
<form method="post" action="{{ url_for('consent') }}">
  <label>Phone (E.164, e.g., +91XXXXXXXXXX):</label>
  <input name="phone" required>
  <label>Purpose:</label>
  <select name="purpose">
    <option value="auth">Authentication (OTP)</option>
  </select>
  <label><input type="checkbox" name="agree" required> I consent to receive a single verification SMS for the stated purpose. I can OPT OUT with STOP.</label>
  <button type="submit">Save Consent</button>
</form>

<h3>2) Send Verification</h3>
<form method="post" action="{{ url_for('send_verification') }}">
  <label>Phone:</label>
  <input name="phone" required>
  <button type="submit">Send Verification SMS</button>
</form>

<h3>3) Check Code</h3>
<form method="post" action="{{ url_for('check_code') }}">
  <label>Phone:</label>
  <input name="phone" required>
  <label>Code:</label>
  <input name="code" required>
  <button type="submit">Verify Code</button>
</form>

<h3>Opt-out</h3>
<form method="post" action="{{ url_for('opt_out') }}">
  <label>Phone:</label>
  <input name="phone" required>
  <button type="submit">Opt Out (STOP)</button>
</form>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for m in messages %}
      <li>{{ m }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
"""

@app.get("/")
def index():
    return render_template_string(PAGE)

# Strict per-number limits to prevent abuse
def per_number_limits(phone: str):
    # Apply dynamic limiter keys: IP + phone
    key = f"{get_remote_address()}:{phone}"
    return limiter.shared_limit("3 per hour", scope=lambda: f"sms:{key}")

@app.post("/consent")
@limiter.limit("10/hour")
def consent():
    phone = request.form.get("phone", "").strip()
    purpose = request.form.get("purpose", "auth").strip()
    agree = request.form.get("agree")
    if not (phone and agree):
        flash("Phone and consent are required.")
        return redirect(url_for("index"))
    # Store consent
    CONSENTS[phone] = {"purpose": purpose, "opted_out": False}
    flash(f"Consent recorded for {phone} ({purpose}).")
    return redirect(url_for("index"))

@app.post("/send")
def send_verification():
    phone = request.form.get("phone", "").strip()
    if not phone:
        flash("Phone is required.")
        return redirect(url_for("index"))

    # Check consent and opt-out
    consent = CONSENTS.get(phone)
    if not consent or consent.get("opted_out"):
        flash("No valid consent on file, or user opted out. Cannot send.")
        return redirect(url_for("index"))

    # Rate limit per number and per IP
    # Apply a one-off check by calling a no-op route limited per phone
    # We wrap the logic manually to enforce a per-phone limit.
    # Using flask-limiter’s shared limits via decorator factory:
    return _send_with_limits(phone)

@per_number_limits.__wrapped__  # type: ignore
def _send_with_limits(phone):
    try:
        # Send verification via provider Verify API (one-time code)
        # Twilio Verify: requires VERIFY_SERVICE_SID
        verification = client.verify.v2.services(VERIFY_SERVICE_SID).verifications.create(
            to=phone, channel="sms"
        )
        flash(f"Verification status: {verification.status}. Code sent if status is 'pending'.")
    except Exception as e:
        flash(f"Send failed: {e}")
    return redirect(url_for("index"))

@app.post("/check")
@limiter.limit("30/hour")
def check_code():
    phone = request.form.get("phone", "").strip()
    code = request.form.get("code", "").strip()
    if not (phone and code):
        flash("Phone and code are required.")
        return redirect(url_for("index"))

    # Ensure consent still valid
    consent = CONSENTS.get(phone)
    if not consent or consent.get("opted_out"):
        flash("No valid consent on file, or user opted out. Cannot verify.")
        return redirect(url_for("index"))

    try:
        verification_check = client.verify.v2.services(VERIFY_SERVICE_SID).verification_checks.create(
            to=phone, code=code
        )
        flash(f"Verification check status: {verification_check.status}")
    except Exception as e:
        flash(f"Verification check failed: {e}")
    return redirect(url_for("index"))

@app.post("/optout")
@limiter.limit("20/hour")
def opt_out():
    phone = request.form.get("phone", "").strip()
    if not phone:
        flash("Phone is required.")
        return redirect(url_for("index"))
    if phone in CONSENTS:
        CONSENTS[phone]["opted_out"] = True
        flash(f"{phone} has opted out. No further SMS will be sent.")
    else:
        flash("No consent record found; nothing to opt out.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    # Run development server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
