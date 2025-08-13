import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. HTML and CSS Template (All in one) ---
INDEX_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cold Room AI Monitor</title>
    
    <!-- Font Import for "Rubber Stamp" style -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Permanent+Marker&family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
    
    <style>
        /* --- Global Style & Color Palette (Red Theme) --- */
        :root {
            --bg-color: #2a2a2a;
            --primary-widget-color: #333333;
            --text-color: #f5f5f5;
            --text-secondary-color: #aaaaaa;
            --border-color: #444444;
            --accent-color-red: #e53935; /* Primary Red */
            --accent-hover-red: #c62828; /* Darker Red for hover */
            --accent-color-yellow: #fdd835; /* Yellow for contrast */
            --risk-high-color: #e53935;
            --risk-medium-color: #fdd835;
            --risk-low-color: #43a047;
            /* Font for body text - clean and readable */
            --font-family-sans: 'Roboto', -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            /* Font for the title - stylized stamp look */
            --font-family-stamp: 'Permanent Marker', cursive;
        }

        html {
            scroll-behavior: smooth;
        }

        body { 
            font-family: var(--font-family-sans);
            margin: 0; 
            padding: 2em; 
            background-color: var(--bg-color); 
            color: var(--text-color); 
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        /* --- Layout & Main Widgets --- */
        .container { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 2em; 
        }

        .main, .sidebar { 
            padding: 2em; 
            border: 1px solid var(--border-color); 
            border-radius: 16px;
            background-color: var(--primary-widget-color); 
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }

        .main { flex-grow: 1; min-width: 400px; }
        .sidebar { width: 320px; flex-shrink: 0; }

        /* --- Typography --- */
        h1 { 
            font-family: var(--font-family-stamp); /* <-- FONT CHANGED HERE */
            color: #fff; 
            text-align: left; 
            margin-bottom: 1em; 
            font-size: 2.8em;
            font-weight: normal; /* The stamp font has its own weight */
            letter-spacing: 2px;
            color: var(--accent-color-red);
        }

        h2, h3 { 
            border-bottom: none;
            padding-bottom: 0;
            margin-bottom: 1.5em;
            color: var(--text-secondary-color); 
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.9em;
            letter-spacing: 1px;
        }
        
        h3.ai-analysis-title {
            color: var(--text-color);
            text-transform: none;
            font-size: 1.2em;
            letter-spacing: normal;
        }

        hr {
            border: none;
            border-top: 1px solid var(--border-color);
            margin: 2em 0;
        }

        /* --- Forms & Interactive Elements --- */
        form { 
            display: grid; 
            gap: 1em; 
        }

        label { 
            font-weight: 500; 
            color: var(--text-secondary-color); 
            font-size: 0.9em;
        }

        input[type="number"], select { 
            padding: 12px; 
            border-radius: 8px; 
            border: 1px solid var(--border-color); 
            background-color: var(--bg-color);
            color: var(--text-color);
            width: 100%;
            box-sizing: border-box;
            font-size: 1em;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        input[type="number"]:focus, select:focus {
            outline: none;
            border-color: var(--accent-color-red);
            box-shadow: 0 0 0 3px rgba(229, 57, 53, 0.3);
        }

        button { 
            padding: 12px; 
            background-color: var(--accent-color-red);
            color: white; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer;
            font-size: 1em; 
            font-weight: bold;
            transition: background-color 0.2s ease;
        }

        button:hover {
            background-color: var(--accent-hover-red);
        }

        /* --- Specific UI Components --- */
        .live-data { 
            font-size: 2.5em; 
            margin: 0.5em 0 1em 0; 
            text-align: center; 
            font-weight: 300;
        }

        .live-data span { 
            font-weight: 600; 
            color: var(--text-color); 
        }
        
        .ai-analysis-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5em;
            text-align: center;
        }
        
        .ai-analysis-item p {
            margin: 0 0 0.5em 0;
            color: var(--text-secondary-color);
            font-size: 1em;
        }

        .ai-analysis-item b { 
            font-size: 1.2em; 
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
            color: #fff;
            display: inline-block;
        }

        #spoilage-risk.High { background-color: var(--risk-high-color); }
        #spoilage-risk.Medium { background-color: var(--risk-medium-color); }
        #spoilage-risk.Low { background-color: var(--risk-low-color); }
        #anomaly-status { background-color: #555; }


        #alert-list { 
            list-style-type: none; 
            padding-left: 0; 
            max-height: 250px; 
            overflow-y: auto; 
        }

        #alert-list li { 
            background-color: var(--bg-color); 
            margin-bottom: 8px;
            padding: 12px; 
            border-radius: 6px; 
            border-left: 3px solid var(--accent-color-red);
            font-size: 0.9em;
        }
    </style>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
</head>
<body>
    <h1>Cold Room Dashboard</h1>
    <div class="container">
        <div class="main">
            <h2>Live Status</h2>
            <div class="live-data">
                🌡 Temp: <span id="current-temp">{{ reading.temperature if reading else 'N/A' }}</span>°C &nbsp;&nbsp;
                💧 Humidity: <span id="current-hum">{{ reading.humidity if reading else 'N/A' }}</span>%
            </div>
            
            <h3 class="ai-analysis-title">AI Analysis</h3>
            <div class="ai-analysis-grid">
                <div class="ai-analysis-item">
                    <p>Spoilage Risk</p>
                    <b id="spoilage-risk" class="{{ spoilage_risk }}">{{ spoilage_risk }}</b>
                </div>
                <div class="ai-analysis-item">
                     <p>Anomaly Status</p>
                     <b id="anomaly-status">{{ anomaly_status.split('(')[0].strip() }}</b>
                </div>
            </div>
            
            <hr>

            <h2>Historical Data (Last 100 Readings)</h2>
            <div class="chart-container" style="position: relative; height:300px; width:100%">
                 <canvas id="dataChart"></canvas>
            </div>
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
            {% if weather and not weather.error %}
                <h4>{{ weather.location }}</h4>
                <p>Temp: {{ weather.temperature }}°C | Humidity: {{ weather.humidity }}%</p>
                <p>Conditions: {{ weather.description|title }}</p>
            {% elif weather %}
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
                
                const tempGradient = ctx.createLinearGradient(0, 0, 0, 300);
                tempGradient.addColorStop(0, 'rgba(229, 57, 53, 0.4)');
                tempGradient.addColorStop(1, 'rgba(229, 57, 53, 0)');

                const humGradient = ctx.createLinearGradient(0, 0, 0, 300);
                humGradient.addColorStop(0, 'rgba(253, 216, 53, 0.4)');
                humGradient.addColorStop(1, 'rgba(253, 216, 53, 0)');

                Chart.defaults.color = '#aaaaaa';
                Chart.defaults.font.family = 'Roboto', -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;

                dataChart = new Chart(ctx, {
                    type: 'line', 
                    data: {
                        labels: chartData.labels,
                        datasets: [
                            {
                                label: 'Temperature (°C)',
                                data: chartData.temperatures,
                                borderColor: '#e53935', 
                                backgroundColor: tempGradient,
                                fill: true,
                                tension: 0.4, 
                                yAxisID: 'y',
                                pointBackgroundColor: '#e53935'
                            },
                            {
                                label: 'Humidity (%)',
                                data: chartData.humidities,
                                borderColor: '#fdd835', 
                                backgroundColor: humGradient,
                                fill: true,
                                tension: 0.4, 
                                yAxisID: 'y1',
                                pointBackgroundColor: '#fdd835'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                type: 'linear', display: true, position: 'left',
                                title: { display: true, text: 'Temperature (°C)' },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' }
                            },
                            y1: {
                                type: 'linear', display: true, position: 'right',
                                title: { display: true, text: 'Humidity (%)' },
                                grid: { drawOnChartArea: false }
                            },
                            x: {
                                type: 'time',
                                time: { unit: 'minute', displayFormats: { minute: 'HH:mm' } },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' },
                                ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 15 }
                            }
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
                    window.location.href = window.location.href; 
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


# --- NEW: Email Alert Configuration ---
# IMPORTANT: For security, use environment variables instead of hardcoding credentials.
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', "your_email@gmail.com")
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL', "receiver_email@example.com")
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', "your_app_password") # Use a Gmail "App Password"


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


# --- 4. Helper Functions (with ENHANCED AI Logic & Email Alerts) ---


def send_email_alert(alert_message):
    """Sends an alert email using Gmail's SMTP server."""
    print("="*20 + f"\\nEMAIL ALERT TRIGGERED: {alert_message}\\n" + "="*20)
    
    if not all([SENDER_EMAIL, RECEIVER_EMAIL, EMAIL_PASSWORD]):
        print("DEBUG: Email credentials not set. Skipping email.")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = "Cold Room AI Monitor - ALERT"
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL

    text = f"""
    Hi,

    This is an automated alert from the Cold Room AI Monitoring system.
    
    An anomaly has been detected:
    ---
    {alert_message}
    ---
    
    Please check the system immediately.
    """
    
    part = MIMEText(text, "plain")
    message.attach(part)
    
    server = None 
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        print(f"Email alert sent successfully to {RECEIVER_EMAIL}!")
    except Exception as e:
        print(f"ERROR: An error occurred while sending email: {e}")
    finally:
        if server:
            server.quit()



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
    if temperature > 4: risk_score += (temperature - 4) * 10
    if temperature < 0: risk_score += abs(temperature) * 15
    if humidity > 95: risk_score += (humidity - 95) * 5
    if humidity < 85: risk_score += (85 - humidity) * 5
    
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
    
    temp_strain_allowance = 0
    if external_temp and external_temp > 20:
        temp_strain_allowance = ((external_temp - 20) / 5) * 0.1
        
    NORMAL_TEMP_MAX = NORMAL_TEMP_MAX_BASE + temp_strain_allowance
    
    if not (NORMAL_TEMP_MIN <= temperature <= NORMAL_TEMP_MAX):
        return True, f"Temperature {temperature}°C is out of the acceptable range ({NORMAL_TEMP_MIN:.1f}°C - {NORMAL_TEMP_MAX:.1f}°C)."
    if not (NORMAL_HUMIDITY_MIN <= humidity <= NORMAL_HUMIDITY_MAX):
        return True, f"Humidity {humidity}% is out of the acceptable range ({NORMAL_HUMIDITY_MIN}% - {NORMAL_HUMIDITY_MAX}%)."
        
    return False, f"Conditions are Normal (Max Temp adjusted to {NORMAL_TEMP_MAX:.1f}°C due to weather)"



# --- 5. Flask Routes ---
@app.route('/')
def index():
    """Renders the main dashboard, now handling location selection."""
    locations = [
        "Bhoranj,IN", "Bilaspur,IN", "Chamba,IN", "Hamirpur,IN", "Kangra,IN", 
        "Kinnaur,IN", "Kullu,IN", "Lahaul and Spiti,IN", "Mandi,IN", 
        "Shimla,IN", "Sirmaur,IN", "Solan,IN", "Una,IN"
    ]
    
    selected_location = request.args.get('location', 'Bhoranj,IN') 
    if selected_location not in locations:
        selected_location = "Bhoranj,IN" 
        
    weather_data = get_weather_forecast(selected_location)
    latest_reading = SensorReading.query.order_by(SensorReading.timestamp.desc()).first()
    alerts = AlertLog.query.order_by(AlertLog.timestamp.desc()).limit(10).all()
    
    spoilage_risk = "N/A"
    anomaly_status = "N/A"
    
    if latest_reading:
        external_temp = weather_data.get('temperature')
        spoilage_risk = predict_spoilage(latest_reading.temperature, latest_reading.humidity, external_temp)
        _, anomaly_status = detect_anomaly(latest_reading.temperature, latest_reading.humidity, external_temp)
        
    return render_template_string(
        INDEX_HTML_TEMPLATE, reading=latest_reading, alerts=alerts, weather=weather_data,
        spoilage_risk=spoilage_risk, anomaly_status=anomaly_status,
        locations=locations, selected_location=selected_location
    )



@app.route('/data', methods=['POST'])
def add_data():
    """Endpoint to receive new sensor data and trigger intelligent alerts."""
    try:
        temp = float(request.form['temperature'])
        humidity = float(request.form['humidity'])
        
        weather_data = get_weather_forecast()
        external_temp = weather_data.get('temperature')
        
        reading = SensorReading(temperature=temp, humidity=humidity)
        db.session.add(reading)
        
        is_anomaly, anomaly_reason = detect_anomaly(temp, humidity, external_temp)
        
        if is_anomaly:
            send_email_alert(anomaly_reason)
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
    readings.reverse()
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

