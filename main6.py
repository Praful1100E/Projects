import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# --- 1. HTML and JavaScript Template ---
INDEX_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cold Room AI Monitor</title>
    <style>
        body { font-family: sans-serif; margin: 2em; background-color: #f4f4f9; color: #333; }
        .container { display: flex; flex-wrap: wrap; gap: 2em; }
        .main, .sidebar { padding: 1.5em; border: 1px solid #ccc; border-radius: 8px; background-color: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .main { flex-grow: 1; min-width: 400px; }
        .sidebar { width: 320px; }
        h1 { color: #2c3e50; }
        h2, h3 { border-bottom: 2px solid #eee; padding-bottom: 0.5em; color: #34495e; }
        form { display: grid; gap: 0.8em; }
        input[type="number"] { padding: 8px; border-radius: 4px; border: 1px solid #ccc; }
        button { padding: 10px; background-color: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1em; }
        button:hover { background-color: #2980b9; }
        .live-data { font-size: 1.5em; margin: 1em 0; }
        #alert-list { list-style-type: none; padding-left: 0; }
        #alert-list li { background-color: #ecf0f1; margin-bottom: 5px; padding: 8px; border-radius: 4px; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>Cold Room AI Monitor</h1>
    <div class="container">
        <div class="main">
            <h2>Live Status</h2>
            <div class="live-data">
                🌡 Temperature: <span id="current-temp">{{ reading.temperature if reading else 'N/A' }}</span> °C <br>
                💧 Humidity: <span id="current-hum">{{ reading.humidity if reading else 'N/A' }}</span> %
            </div>
            <h3>AI Analysis</h3>
            <p>Spoilage Risk: <b id="spoilage-risk">{{ spoilage_risk }}</b></p>
            <p>Anomaly Status: <b id="anomaly-status">{{ anomaly_status }}</b></p>
            
            <h2>Historical Data (Last 100 Readings)</h2>
            <canvas id="dataChart" width="400" height="200"></canvas>
        </div>
        <div class="sidebar">
            <h3>Manual Data Entry</h3>
            <form id="data-form">
                <label for="temperature">Temperature (°C):</label>
                <input type="number" id="temperature" name="temperature" step="0.1" required>
                <label for="humidity">Humidity (%):</label>
                <input type="number" id="humidity" name="humidity" step="0.1" required>
                <button type="submit">Submit Data</button>
            </form>
            <hr>
            <h3>External Weather: {{ weather.location if not weather.error else 'Error' }}</h3>
            {% if not weather.error %}
                <p>Temp: {{ weather.temperature }}°C | Humidity: {{ weather.humidity }}%</p>
                <p>Conditions: {{ weather.description|title }}</p>
            {% else %}
                <p style="color:red;">{{ weather.error }}</p>
            {% endif %}
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
            const dataForm = document.getElementById('data-form');
            const ctx = document.getElementById('dataChart').getContext('2d');
            let dataChart;

            function createChart(chartData) {
                if (dataChart) dataChart.destroy();
                dataChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: chartData.labels,
                        datasets: [
                            {
                                label: 'Temperature (°C)',
                                data: chartData.temperatures,
                                borderColor: 'rgb(255, 99, 132)',
                                tension: 0.1,
                                yAxisID: 'y'
                            },
                            {
                                label: 'Humidity (%)',
                                data: chartData.humidities,
                                borderColor: 'rgb(54, 162, 235)',
                                tension: 0.1,
                                yAxisID: 'y1'
                            }
                        ]
                    },
                    options: {
                        scales: {
                            y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Temperature (°C)' } },
                            y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Humidity (%)' }, grid: { drawOnChartArea: false } }
                        }
                    }
                });
            }

            async function updateChart() {
                const response = await fetch('/api/historical-data');
                const chartData = await response.json();
                createChart(chartData);
            }
            
            dataForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                const formData = new FormData(dataForm);
                const response = await fetch('/data', { method: 'POST', body: formData });
                const result = await response.json();
                
                if (result.status === 'success') {
                    alert('Data submitted successfully! The page will now refresh.');
                    location.reload();
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


# --- 4. Helper Functions (Services and AI Logic) ---

def send_alert(message):
    """Prints an alert and sends an SMS via Twilio if configured."""
    print("="*20)
    print(f"ALERT TRIGGERED: {message}")
    print("="*20)

    # Note: Twilio credentials still need to be set as environment variables
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
    owner_phone_number = os.environ.get('OWNER_PHONE_NUMBER')

    if not all([account_sid, auth_token, twilio_phone_number, owner_phone_number]):
        print("DEBUG: Twilio environment variables are not fully set. Skipping SMS.")
        return

    print("DEBUG: All Twilio variables found. Attempting to send SMS...")
    try:
        client = Client(account_sid, auth_token)
        sms = client.messages.create(
            body=f"Cold Storage Alert: {message}",
            from_=twilio_phone_number,
            to=owner_phone_number
        )
        print(f"SMS sent successfully to {owner_phone_number}! SID: {sms.sid}")
    except TwilioRestException as e:
        print(f"ERROR: Failed to send SMS due to a Twilio error: {e}")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while sending SMS: {e}")


def get_weather_forecast(location="Hamirpur,IN"):
    """
    Fetches weather data using the logic from your provided script.
    """
    # --- MODIFICATION: Using your new API key and logic ---
    # WARNING: Hardcoding API keys is a security risk.
    API_KEY = "32322b3a704cf8713c242c2f1c2bfae7"
    BASE_URL = "http://api.openweathermap.org/data/2.5/weather"
    
    # Create the complete API URL using the location parameter
    url = f"{BASE_URL}?q={location}&appid={API_KEY}&units=metric"
    
    try:
        response = requests.get(url)
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            # Return data in the format the Flask template expects
            return {
                "location": data['name'],
                "temperature": data['main']['temp'],
                "humidity": data['main']['humidity'],
                "description": data['weather'][0]['description']
            }
        else:
            # Return an error message if the request failed
            error_message = response.json().get('message', response.text)
            return {"error": f"API Error: {error_message}"}
            
    except requests.exceptions.RequestException as e:
        # Handle network-related errors
        return {"error": f"Could not fetch weather: {e}"}

def predict_spoilage(temperature, humidity):
    risk_score = 0
    if temperature > 4: risk_score += (temperature - 4) * 10
    if temperature < 0: risk_score += abs(temperature) * 15
    if humidity > 95: risk_score += (humidity - 95) * 5
    if humidity < 85: risk_score += (85 - humidity) * 5
    if risk_score > 70: return "High"
    elif risk_score > 30: return "Medium"
    return "Low"

def detect_anomaly(temperature, humidity):
    NORMAL_TEMP_MIN, NORMAL_TEMP_MAX = 0, 4
    NORMAL_HUMIDITY_MIN, NORMAL_HUMIDITY_MAX = 90, 95
    if not (NORMAL_TEMP_MIN <= temperature <= NORMAL_TEMP_MAX):
        return True, f"Temp {temperature}°C is out of range ({NORMAL_TEMP_MIN}-{NORMAL_TEMP_MAX}°C)."
    if not (NORMAL_HUMIDITY_MIN <= humidity <= NORMAL_HUMIDITY_MAX):
        return True, f"Humidity {humidity}% is out of range ({NORMAL_HUMIDITY_MIN}-{NORMAL_HUMIDITY_MAX}%)."
    return False, "Conditions are Normal"


# --- 5. Flask Routes ---
@app.route('/')
def index():
    latest_reading = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
    alerts = AlertLog.query.order_by(AlertLog.timestamp.desc()).limit(10).all()
    # This now calls your new weather function
    weather_data = get_weather_forecast() 
    
    spoilage_risk = "N/A"
    anomaly_status = "N/A"
    if latest_reading:
        spoilage_risk = predict_spoilage(latest_reading.temperature, latest_reading.humidity)
        _, anomaly_status = detect_anomaly(latest_reading.temperature, latest_reading.humidity)

    return render_template_string(
        INDEX_HTML_TEMPLATE, 
        reading=latest_reading, 
        alerts=alerts, 
        weather=weather_data,
        spoilage_risk=spoilage_risk,
        anomaly_status=anomaly_status
    )

@app.route('/data', methods=['POST'])
def add_data():
    try:
        temp = float(request.form['temperature'])
        humidity = float(request.form['humidity'])
        reading = SensorReading(temperature=temp, humidity=humidity)
        db.session.add(reading)

        is_anomaly, anomaly_reason = detect_anomaly(temp, humidity)
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
    readings = SensorReading.query.order_by(SensorReading.timestamp.asc()).limit(100).all()
    return jsonify({
        'labels': [r.timestamp.strftime('%H:%M:%S') for r in readings],
        'temperatures': [r.temperature for r in readings],
        'humidities': [r.humidity for r in readings]
    })


# --- 6. Main Execution Block ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)