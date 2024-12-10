from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import logging
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

# -----------------------------
# Logging Configuration
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# Database Configuration
# -----------------------------

# Hardcoded PostgreSQL credentials
DB_USERNAME = 'postgres'          # Replace with your PostgreSQL username
DB_PASSWORD = 'Passwordd'         # Replace with your PostgreSQL password
DB_HOST = '34.172.199.238'        # Replace with your PostgreSQL host, e.g., 'localhost'
DB_PORT = '5432'                  # Replace with your PostgreSQL port if different
DB_NAME = 'postgres'              # Replace with your PostgreSQL database name

# Construct the Database URI
db_uri = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

# Log the Database URI (Caution: Avoid logging sensitive information in production)
logger.info(f"Connecting to the database at: {db_uri}")

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
    __table_args__ = (
        db.Index('idx_timestamp', 'timestamp'),
    )
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
    logger.info(f"Received data: {data}")
    
    name = data.get('name')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if name is None or latitude is None or longitude is None:
        logger.error("Name, latitude, and longitude are required.")
        return {'status': 'error', 'message': 'Name, latitude, and longitude are required.'}, 400

    # Validate latitude and longitude
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except ValueError:
        logger.error("Invalid latitude or longitude format.")
        return {'status': 'error', 'message': 'Invalid latitude or longitude format.'}, 400

    # Find existing location by name
    location = Location.query.filter_by(name=name).first()
    if location:
        logger.info(f"Updating existing location: {name}")
        location.latitude = latitude
        location.longitude = longitude
        location.timestamp = datetime.utcnow()
    else:
        logger.info(f"Creating new location: {name}")
        # Create new location
        location = Location(latitude=latitude, longitude=longitude, name=name)
        db.session.add(location)
    
    try:
        db.session.commit()
        logger.info(f"Database commit successful for location: {name}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database commit failed for location: {name}", exc_info=True)
        return {'status': 'error', 'message': 'Database commit failed.'}, 500

    # Call Google Maps Directions API
    origin = f"{latitude},{longitude}"
    destination = f"{DESTINATION_LAT},{DESTINATION_LON}"
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={GOOGLE_MAPS_API_KEY}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        directions = response.json()
        try:
            duration = directions['routes'][0]['legs'][0]['duration']['text']
        except (IndexError, KeyError):
            duration = "Unknown"
            logger.warning("Duration information is missing in the Google Maps API response.")
    except requests.exceptions.RequestException as e:
        duration = "API Error"
        logger.error("Failed to get directions from Google Maps API.", exc_info=True)

    # Emit the new location and duration
    socketio.emit('new_location', {
        'id': location.id,
        'lat': location.latitude,
        'lon': location.longitude,
        'name': location.name,
        'timestamp': location.timestamp.isoformat(),
        'duration': duration
    })
    logger.info(f"Emitted new_location event for: {name} with duration: {duration}")
    
    return {'status': 'success', 'duration': duration}

@app.route('/get_all_locations', methods=['GET'])
def get_all_locations():
    try:
        locations = Location.query.all()
        data = [{
            'id': loc.id,
            'latitude': loc.latitude,
            'longitude': loc.longitude,
            'name': loc.name,
            'timestamp': loc.timestamp.isoformat()
        } for loc in locations]
        logger.info(f"Fetched all locations: {len(data)} records.")
        return {'locations': data}
    except Exception as e:
        logger.error("Failed to fetch all locations.", exc_info=True)
        return {'status': 'error', 'message': 'Failed to fetch locations.'}, 500

@app.route('/get_latest_location', methods=['GET'])
def get_latest_location():
    try:
        latest_location = Location.query.order_by(Location.timestamp.desc()).first()
        if latest_location:
            logger.info(f"Fetched latest location: {latest_location.name}")
            return {
                'id': latest_location.id,
                'latitude': latest_location.latitude,
                'longitude': latest_location.longitude,
                'name': latest_location.name,
                'timestamp': latest_location.timestamp.isoformat()
            }
        else:
            logger.info("No locations found in the database.")
            # Return a default location if no records exist
            return {
                'id': None,
                'latitude': '0',
                'longitude': '0',
                'name': 'Default Location',
                'timestamp': None
            }
    except Exception as e:
        logger.error("Failed to fetch the latest location.", exc_info=True)
        return {'status': 'error', 'message': 'Failed to fetch the latest location.'}, 500

@app.route('/send_notification', methods=['POST'])
def send_notification():
    data = request.json
    name = data.get('name')
    message = data.get('message', 'Live Location')

    if name is None:
        logger.error("Name is required to send a notification.")
        return {'status': 'error', 'message': 'Name is required.'}, 400

    # Fetch the latest location for the given name
    location = Location.query.filter_by(name=name).order_by(Location.timestamp.desc()).first()
    if location:
        message = f"{name}'s current location: ({location.latitude}, {location.longitude})"
        logger.info(f"Sending notification for {name}: {message}")
    else:
        message = f"No location data found for {name}."
        logger.warning(f"Attempted to send notification for nonexistent location: {name}")

    def send_pushover_notification(user_key, app_token, message):
        url = "https://api.pushover.net/1/messages.json"
        data = {
            "token": app_token,
            "user": user_key,
            "message": message,
            "priority": "-1"
        }
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            logger.info("Pushover notification sent successfully.")
        except requests.exceptions.RequestException as e:
            logger.error("Failed to send Pushover notification.", exc_info=True)

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
