import requests

API_KEY = "32322b3a704cf8713c242c2f1c2bfae7"
BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

# Change this to your desired city
city = "Delhi"

# Create the complete API URL
url = f"{BASE_URL}?q={city}&appid={API_KEY}&units=metric"

# Make the GET request
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    main = data['main']
    temperature = main['temp']
    humidity = main['humidity']
    description = data['weather'][0]['description']

    print(f"Weather in {city}:")
    print(f"Temperature: {temperature}°C")
    print(f"Humidity: {humidity}%")
    print(f"Condition: {description}")
else:
    print("Error:", response.status_code, response.text)