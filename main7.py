import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# --- 1. HTML and JavaScript Template (with Dark Theme and Location Selector) ---
INDEX_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cold Room AI Monitor - Dark Mode</title>
    <style>
        :root {
            --bg-color: #1a1a1a;
            --primary-widget-color: #2c2c2c;
            --secondary-widget-color: #252525;
            --text-color: #e0e0e0;
            --text-secondary-color: #b0b0b0;
            --border-color: #444;
            --accent-color: #007bff;
            --accent-hover-color: #0056b3;
            --risk-high-color: #e74c3c;
            --risk-medium-color: #f39c12;
            --risk-low-color: #2ecc71;
        }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; 
            margin: 0; 
            padding: 2em; 
            background-color: var(--bg-color); 
            color: var(--text-color); 
        }
        .container { display: flex; flex-wrap: wrap; gap: 2em; }
        .main, .sidebar { padding: 1.5em; border: 1px solid var(--border-color); border-radius: 12px; background-color: var(--primary-widget-color); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        .main { flex-grow: 1; min-width: 400px; }
        .sidebar { width: 320px; }
        h1 { color: #fff; text-align: center; margin-bottom: 1em; }
        h2, h3 { border-bottom: 2px solid var(--border-color); padding-bottom: 0.5em; color: #fff; }
        form { display: grid; gap: 1em; }
        label { font-weight: bold; color: var(--text-secondary-color); }
        input[type="number"], select { 
            padding: 10px; 
            border-radius: 6px; 
            border: 1px solid var(--border-color); 
            background-color: var(--secondary-widget-color);
            color: var(--text-color);
            width: 100%;
            box-sizing: border-box;
        }
        button { 
            padding: 12px; 
            background-color: var(--accent-color); 
            color: white; 
            border: none; 
            border-radius: 6px; 
            cursor: pointer; 
            font-size: 1.1em; 
            font-weight: bold;
            transition: background-color 0.2s;
        }
        button:hover { background-color: var(--accent-hover-color); }
        .live-data { font-size: 1.8em; margin: 1em 0; text-align: center; }
        .live-data span { font-weight: bold; color: #fff; }
        .ai-analysis b { font-size: 1.2em; }
        #spoilage-risk.High { color: var(--risk-high-color); }
        #spoilage-risk.Medium { color: var(--risk-medium-color); }
        #spoilage-risk.Low { color: var(--risk-low-color); }
        #alert-list { list-style-type: none; padding-left: 0; max-height: 200px; overflow-y: auto; }
        #alert-list li { background-color: var(--secondary-widget-color); margin-bottom: 8px; padding: 10px; border-radius: 6px; border-left: 4px solid var(--accent-color); }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
</head>
<body>
    <h1>🍎 Cold Room AI Monitor</h1>
    <div class="container">
        <div class="main">
            <h2>Live Status</h2>
            <div class="live-data">
                🌡 Temp: <span id="current-temp">{{ reading.temperature if reading else 'N/A' }}</span> °C&nbsp;&nbsp;&nbsp;
                💧 Humidity: <span id="current-hum">{{ reading.humidity if reading else 'N/A' }}</span> %
            </div>
            
            <h3 class="ai-analysis">AI Analysis (Factoring in External Weather)</h3>
            <p>Spoilage Risk: <b id="spoilage-risk" class="{{ spoilage_risk }}">{{ spoilage_risk }}</b></p>
            <p>Anomaly Status: <b id="anomaly-status">{{ anomaly_status }}</b></p>
            
            <h2>Historical Data (Last 100 Readings)</h2>
            <canvas id="dataChart" width="400" height="200"></canvas>
        </div>
        <div class="sidebar">
            <h3>Weather Station</h3>
            <form id="location-form">
                <label for="location">Select Location:</label>
                <select id="location" name="location">
                    {% for loc in locations %}
                    <option value="{{ loc }}" {% if loc == selected_location %}selected{% endif %}>{{ loc.split(',')[0] }}</option>
                    {% endfor %}
                </select>
                <button type="submit">Get Weather</button>
            </form>
            <hr>
            {% if not weather.error %}
                <h4>{{ weather.location }}</h4>
                <p>Temp: {{ weather.temperature }}°C | Humidity: {{ weather.humidity }}%</p>
                <p>Conditions: {{ weather.description|title }}</p>
            {% else %}
                <p style="color:var(--risk-high-color);">{{ weather.error }}</p>
            {% endif %}
            <hr>
            <h3>Manual Data Entry</h3>
            <form id="data-form">
                <label for="temperature">Internal Temp (°C):</label>
                <input type="number" id="temperature" name="temperature" step="0.1" required>
                <label for="humidity">Internal Humidity (%):</label>
                <input type="number" id="humidity" name="humidity" step="0.1" required>
                <button type="submit">Submit Data</button>
            </form>
            <hr>
            <h3>Recent Alerts</h3>
            <ul id="alert-list">
                {% for alert in alerts %}
                    <li><small>{{ alert.timestamp.strftime('%Y-%m-%d %H:%M') }}</small>: {{ alert.message }}</li>
                {% else %}
                    <li>No recent alerts.</li>
                {% endfor %}
            </ul>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function () {
            // --- Location Change Handler ---
            document.getElementById('location-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const selectedLocation = document.getElementById('location').value;
                window.location.href = '/?location=' + encodeURIComponent(selectedLocation);
            });

            // --- Chart.js Setup ---
            const ctx = document.getElementById('dataChart').getContext('2d');
            let dataChart;

            function createChart(chartData) {
                if (dataChart) dataChart.destroy();
                Chart.defaults.color = 'rgba(224, 224, 224, 0.8)';
                dataChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: chartData.labels,
                        datasets: [
                            {
                                label: 'Temperature (°C)', data: chartData.temperatures,
                                borderColor: 'rgb(255, 99, 132)', backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                tension: 0.1, yAxisID: 'y', borderWidth: 2
                            },
                            {
                                label: 'Humidity (%)', data: chartData.humidities,
                                borderColor: 'rgb(54, 162, 235)', backgroundColor: 'rgba(54, 162, 235, 0.2)',
                                tension: 0.1, yAxisID: 'y1', borderWidth: 2
                            }
                        ]
                    },
                    options: {
                        scales: {
                            y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Temperature (°C)' }, grid: { color: 'rgba(255, 255, 255, 0.1)' } },
                            y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Humidity (%)' }, grid: { drawOnChartArea: false, color: 'rgba(255, 255, 255, 0.1)' } },
                            x: { grid: { color: 'rgba(255, 255, 255, 0.1)' } }
                        }
                    }
                });
            }

            async function updateChart() {
                const response = await fetch('/api/historical-data');
                const chartData = await response.json();
                createChart(chartData);
            }
            
            // --- Manual Data Form Submission ---
            document.getElementById('data-form').addEventListener('submit', async function (e) {
                e.preventDefault();
                const formData = new FormData(e.target);
                const response = await fetch('/data', { method: 'POST', body: formData });
                const result = await response.json();
                
                if (result.status === 'success') {
                    alert('Data submitted successfully! The page will now refresh.');
                    window.location.href = window.location.href; // Refresh page with current query params
                } else {
                    alert('Error submitting data: ' + result.message);
                }
            });

            updateChart();
        });
    </script>
</body>
</html>
"""


# --- 2. Flask App Initialization and Configuration ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'cold_storage.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- 3. Database Models ---
class SensorReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

class AlertLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)


# --- 4. Helper Functions (with ENHANCED AI Logic) ---

def send_alert(message):
    """Prints an alert and sends an SMS via Twilio if configured."""
    print("="*20 + f"\nALERT TRIGGERED: {message}\n" + "="*20)
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
    owner_phone_number = os.environ.get('OWNER_PHONE_NUMBER')
    if not all([account_sid, auth_token, twilio_phone_number, owner_phone_number]):
        print("DEBUG: Twilio environment variables not set. Skipping SMS.")
        return
    try:
        client = Client(account_sid, auth_token)
        sms = client.messages.create(body=f"Cold Storage Alert: {message}", from_=twilio_phone_number, to=owner_phone_number)
        print(f"SMS sent successfully! SID: {sms.sid}")
    except TwilioRestException as e:
        print(f"ERROR: Failed to send SMS via Twilio: {e}")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while sending SMS: {e}")

def get_weather_forecast(location="Bhoranj,IN"):
    """ Fetches weather data for a given location."""
    API_KEY = "32322b3a704cf8713c242c2f1c2bfae7" # Using your provided key
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"
    url = f"{BASE_URL}?q={location}&appid={API_KEY}&units=metric"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return {
                "location": data.get('name', 'Unknown'), "temperature": data['main']['temp'],
                "humidity": data['main']['humidity'], "description": data['weather'][0]['description'],
                "error": None
            }
        else:
            return {"error": f"Weather API error: {response.json().get('message', 'Unknown error')}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error fetching weather: {e}"}

def predict_spoilage(temperature, humidity, external_temp=None):
    """Predicts spoilage risk, now considering external temperature."""
    risk_score = 0
    # Base risk from internal conditions
    if temperature > 4: risk_score += (temperature - 4) * 10
    if temperature < 0: risk_score += abs(temperature) * 15
    if humidity > 95: risk_score += (humidity - 95) * 5
    if humidity < 85: risk_score += (85 - humidity) * 5
    
    # Add extra risk based on external heat putting strain on the system
    if external_temp and external_temp > 25:
        strain_factor = (external_temp - 25) * 1.5
        risk_score += strain_factor
        print(f"DEBUG: External temp {external_temp}°C added {strain_factor:.1f} to risk score.")

    if risk_score > 70: return "High"
    if risk_score > 30: return "Medium"
    return "Low"

def detect_anomaly(temperature, humidity, external_temp=None):
    """Detects anomalies, with dynamic thresholds based on external weather."""
    NORMAL_TEMP_MIN, NORMAL_TEMP_MAX_BASE = 0, 4
    NORMAL_HUMIDITY_MIN, NORMAL_HUMIDITY_MAX = 90, 95

    # Adjust max temp threshold based on external heat strain
    temp_strain_allowance = 0
    if external_temp and external_temp > 20:
        # Allow 0.1°C extra for every 5°C of heat above 20°C
        temp_strain_allowance = ((external_temp - 20) / 5) * 0.1
    
    NORMAL_TEMP_MAX = NORMAL_TEMP_MAX_BASE + temp_strain_allowance
    
    if not (NORMAL_TEMP_MIN <= temperature <= NORMAL_TEMP_MAX):
        return True, f"Temp {temperature}°C is out of range ({NORMAL_TEMP_MIN:.1f}-{NORMAL_TEMP_MAX:.1f}°C)."
    if not (NORMAL_HUMIDITY_MIN <= humidity <= NORMAL_HUMIDITY_MAX):
        return True, f"Humidity {humidity}% is out of range ({NORMAL_HUMIDITY_MIN}-{NORMAL_HUMIDITY_MAX}%)."
    return False, f"Conditions Normal (Max Temp adjusted to {NORMAL_TEMP_MAX:.1f}°C due to weather)"


# --- 5. Flask Routes (Updated for Location Handling) ---
@app.route('/')
def index():
    """Renders the main dashboard, now handling location selection."""
    # NEW: List of locations for the dropdown
    locations = ["Bhoranj,IN", "Delhi,IN", "Mumbai,IN", "Bangalore,IN", "Kolkata,IN", "Chennai,IN"]
    # NEW: Get selected location from URL, default to Bhoranj
    selected_location = request.args.get('location', 'Bhoranj,IN')
    if selected_location not in locations: # Basic security check
        selected_location = "Bhoranj,IN"

    weather_data = get_weather_forecast(selected_location)
    latest_reading = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
    alerts = AlertLog.query.order_by(AlertLog.timestamp.desc()).limit(10).all()
    
    spoilage_risk = "N/A"
    anomaly_status = "N/A"
    if latest_reading:
        external_temp = weather_data.get('temperature')
        # UPDATED: Pass external temp to AI functions
        spoilage_risk = predict_spoilage(latest_reading.temperature, latest_reading.humidity, external_temp)
        _, anomaly_status = detect_anomaly(latest_reading.temperature, latest_reading.humidity, external_temp)

    return render_template_string(
        INDEX_HTML_TEMPLATE, 
        reading=latest_reading, 
        alerts=alerts, 
        weather=weather_data,
        spoilage_risk=spoilage_risk,
        anomaly_status=anomaly_status,
        locations=locations,
        selected_location=selected_location
    )

@app.route('/data', methods=['POST'])
def add_data():
    """Endpoint to receive new sensor data and trigger intelligent alerts."""
    try:
        temp = float(request.form['temperature'])
        humidity = float(request.form['humidity'])
        
        # Get current weather to factor into the analysis
        # Note: In a real-world scenario, you might pass the location from the form
        weather_data = get_weather_forecast()
        external_temp = weather_data.get('temperature')

        reading = SensorReading(temperature=temp, humidity=humidity)
        db.session.add(reading)

        is_anomaly, anomaly_reason = detect_anomaly(temp, humidity, external_temp)
        if is_anomaly:
            send_alert(anomaly_reason)
            alert_log = AlertLog(message=anomaly_reason)
            db.session.add(alert_log)
        
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/historical-data')
def historical_data():
    readings = SensorReading.query.order_by(SensorReading.timestamp.desc()).limit(100).all()
    readings.reverse() # Show oldest first on the chart
    return jsonify({
        'labels': [r.timestamp.strftime('%Y-%m-%dT%H:%M:%S') for r in readings],
        'temperatures': [r.temperature for r in readings],
        'humidities': [r.humidity for r in readings]
    })


# --- 6. Main Execution Block ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)