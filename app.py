from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# -----------------------------
# Database Configuration
# -----------------------------

# Hardcoded PostgreSQL credentials
DB_USERNAME = 'postgres'          # Replace with your PostgreSQL username
DB_PASSWORD = 'Passwordd'          # Replace with your PostgreSQL password
DB_HOST = '34.172.199.238'                  # Replace with your PostgreSQL host, e.g., 'localhost'
DB_PORT = '5432'                       # Replace with your PostgreSQL port if different
DB_NAME = 'postgres'         # Replace with your PostgreSQL database name

# Construct the Database URI
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# Disable track modifications to suppress warning
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Extensions
socketio = SocketIO(app, cors_allowed_origins="*")
db = SQLAlchemy(app)

# -----------------------------
# Google Maps Configuration
# -----------------------------

GOOGLE_MAPS_API_KEY = "AIzaSyBIZt7GRemJ5z5zRcXMDks7hi3GvXXiwKI"  # Ensure this key is valid
DESTINATION_LAT = 44.987303
DESTINATION_LON = -93.221375

# -----------------------------
# Database Model
# -----------------------------

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    name = db.Column(db.String(100), nullable=False, unique=True)  # Enforce unique names
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Location {self.id} - {self.name}>"

# -----------------------------
# Routes
# -----------------------------

@app.route('/')
def index():
    return render_template('index.html')  # The HTML file with Leaflet and Socket.IO

@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.json
    print(data)
    
    name = data.get('name')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if name is None or latitude is None or longitude is None:
        return {'status': 'error', 'message': 'Name, latitude, and longitude are required.'}, 400

    # Find existing location by name
    location = Location.query.filter_by(name=name).first()
    if location:
        location.latitude = latitude
        location.longitude = longitude
        location.timestamp = datetime.utcnow()
    else:
        # Create new location
        location = Location(latitude=latitude, longitude=longitude, name=name)
        db.session.add(location)
    
    db.session.commit()

    # Call Google Maps Directions API
    origin = f"{latitude},{longitude}"
    destination = f"{DESTINATION_LAT},{DESTINATION_LON}"
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={GOOGLE_MAPS_API_KEY}"
    
    response = requests.get(url)
    if response.status_code == 200:
        directions = response.json()
        try:
            duration = directions['routes'][0]['legs'][0]['duration']['text']
        except (IndexError, KeyError):
            duration = "Unknown"
        
        # Emit the new location and duration
        socketio.emit('new_location', {
            'id': location.id,
            'lat': location.latitude,
            'lon': location.longitude,
            'name': location.name,
            'timestamp': location.timestamp.isoformat(),
            'duration': duration
        })
        
        return {'status': 'success', 'duration': duration}
    else:
        return {'status': 'error', 'message': 'Failed to get directions'}, 500

@app.route('/get_all_locations', methods=['GET'])
def get_all_locations():
    locations = Location.query.all()
    data = [{
        'id': loc.id,
        'latitude': loc.latitude,
        'longitude': loc.longitude,
        'name': loc.name,
        'timestamp': loc.timestamp.isoformat()
    } for loc in locations]
    return {'locations': data}

@app.route('/get_latest_location', methods=['GET'])
def get_latest_location():
    # Optional: Retain if needed
    latest_location = Location.query.order_by(Location.timestamp.desc()).first()
    if latest_location:
        return {
            'id': latest_location.id,
            'latitude': latest_location.latitude,
            'longitude': latest_location.longitude,
            'name': latest_location.name,
            'timestamp': latest_location.timestamp.isoformat()
        }
    else:
        # Return a default location if no records exist
        return {
            'id': None,
            'latitude': '0',
            'longitude': '0',
            'name': 'Default Location',
            'timestamp': None
        }

@app.route('/send_notification', methods=['POST'])
def send_notification():
    data = request.json
    name = data.get('name')
    message = data.get('message', 'Live Location')

    if name is None:
        return {'status': 'error', 'message': 'Name is required.'}, 400

    # Fetch the latest location for the given name
    location = Location.query.filter_by(name=name).order_by(Location.timestamp.desc()).first()
    if location:
        message = f"{name}'s current location: ({location.latitude}, {location.longitude})"
    else:
        message = f"No location data found for {name}."

    def send_pushover_notification(user_key, app_token, message):
        url = "https://api.pushover.net/1/messages.json"
        data = {
            "token": app_token,
            "user": user_key,
            "message": message,
            "priority": "-1"
        }
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("Notification sent successfully.")
        else:
            print(f"Failed to send notification. Status code: {response.status_code}")

    # Replace these with your Pushover User Key and API Token
    USER_KEY = "updpmtd33jnw8jjweqm6f5p526aqam"
    APP_TOKEN = "azfqtfbaypgs7v863jt752gdu5y93e"
    
    # Send the notification
    send_pushover_notification(USER_KEY, APP_TOKEN, message)
    return {'status': 'success'}

# -----------------------------
# Main Entry Point
# -----------------------------

if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
