from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import logging
import os  # Ensure os is imported for environment variables

# -----------------------------
# Flask Application Setup
# -----------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'  # Secret key for session management and security

# -----------------------------
# Logging Configuration
# -----------------------------
# Configure the logging level and format
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  # Create a logger for this module

# -----------------------------
# Database Configuration
# -----------------------------

# Database connection details
# Replace these with your actual PostgreSQL credentials or use environment variables for better security
DB_USERNAME = 'postgres'          # PostgreSQL username
DB_PASSWORD = 'Passwordd'         # PostgreSQL password
DB_HOST = '34.172.199.238'        # PostgreSQL host address
DB_PORT = '5432'                  # PostgreSQL port number
DB_NAME = 'postgres'              # PostgreSQL database name

# Construct the Database URI in the format required by SQLAlchemy
db_uri = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri  # Set the SQLAlchemy database URI

# Log the Database URI for debugging purposes
# **Caution:** Avoid logging sensitive information like passwords in production environments
logger.info(f"Connecting to the database at: {db_uri}")

# Disable SQLAlchemy event system to save resources and suppress warnings
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Flask extensions
socketio = SocketIO(app, cors_allowed_origins="*")  # Initialize Socket.IO for real-time communication
db = SQLAlchemy(app)  # Initialize SQLAlchemy for ORM (Object Relational Mapping)

# -----------------------------
# Google Maps Configuration
# -----------------------------

# Google Maps API Key
# **Caution:** Replace this hardcoded key with an environment variable for enhanced security
GOOGLE_MAPS_API_KEY = "AIzaSyBIZt7GRemJ5z5zRcXMDks7hi3GvXXiwKI"  # Your actual Google Maps API key

# Destination coordinates (Home Location)
DESTINATION_LAT = 44.971808  # Latitude for Blegen
DESTINATION_LON = -93.243360  # Longitude for Blegen

# -----------------------------
# Database Model
# -----------------------------

class Location(db.Model):
    """
    Database model for storing user locations.
    """
    __tablename__ = 'locations'  # Name of the table in the database
    __table_args__ = (
        db.Index('idx_timestamp', 'timestamp'),  # Create an index on the timestamp column for faster queries
    )
    id = db.Column(db.Integer, primary_key=True)  # Primary key column
    latitude = db.Column(db.Float, nullable=False)  # Latitude of the user's location
    longitude = db.Column(db.Float, nullable=False)  # Longitude of the user's location
    name = db.Column(db.String(100), nullable=False, unique=True)  # User's name, enforced to be unique
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Timestamp of the location update

    def __repr__(self):
        """
        Return a string representation of the Location instance.
        """
        return f"<Location {self.id} - {self.name}>"

# -----------------------------
# Routes
# -----------------------------

@app.route('/')
def index():
    """
    Render the main page of the application.
    """
    return render_template('index.html')  # The HTML file with Leaflet and Socket.IO integrations

@app.route('/update_location', methods=['POST'])
def update_location():
    """
    Endpoint to update or add a user's location.
    Expects JSON data with 'name', 'latitude', and 'longitude'.
    """
    data = request.json  # Parse JSON data from the request
    logger.info(f"Received data: {data}")  # Log the received data for debugging
    
    # Extract data from the JSON payload
    name = data.get('name')  # User's name
    latitude = data.get('latitude')  # User's latitude
    longitude = data.get('longitude')  # User's longitude
    
    # Validate that all required fields are present
    if name is None or latitude is None or longitude is None:
        logger.error("Name, latitude, and longitude are required.")
        return {'status': 'error', 'message': 'Name, latitude, and longitude are required.'}, 400  # Bad Request

    # Validate latitude and longitude formats
    try:
        latitude = float(latitude)  # Convert latitude to float
        longitude = float(longitude)  # Convert longitude to float
    except ValueError:
        logger.error("Invalid latitude or longitude format.")
        return {'status': 'error', 'message': 'Invalid latitude or longitude format.'}, 400  # Bad Request

    # Check if the user already exists in the database
    location = Location.query.filter_by(name=name).first()
    if location:
        # Update existing user's location
        logger.info(f"Updating existing location: {name}")
        location.latitude = latitude
        location.longitude = longitude
        location.timestamp = datetime.utcnow()  # Update the timestamp to current UTC time
    else:
        # Create a new user location entry
        logger.info(f"Creating new location: {name}")
        location = Location(latitude=latitude, longitude=longitude, name=name)
        db.session.add(location)  # Add the new location to the session
    
    try:
        db.session.commit()  # Commit the transaction to the database
        logger.info(f"Database commit successful for location: {name}")
    except Exception as e:
        db.session.rollback()  # Rollback the session in case of an error
        logger.error(f"Database commit failed for location: {name}", exc_info=True)
        return {'status': 'error', 'message': 'Database commit failed.'}, 500  # Internal Server Error

    # -----------------------------
    # Google Maps Directions API Call
    # -----------------------------
    # Construct the origin and destination strings for the API request
    origin = f"{latitude},{longitude}"  # User's current location
    destination = f"{DESTINATION_LAT},{DESTINATION_LON}"  # Home location (Blegen)
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={GOOGLE_MAPS_API_KEY}"
    
    try:
        response = requests.get(url)  # Make the GET request to the Directions API
        response.raise_for_status()  # Raise an exception for HTTP error responses
        directions = response.json()  # Parse the JSON response
        try:
            duration = directions['routes'][0]['legs'][0]['duration']['text']  # Extract the duration text
        except (IndexError, KeyError):
            duration = "Unknown"  # Default duration if parsing fails
            logger.warning("Duration information is missing in the Google Maps API response.")
    except requests.exceptions.RequestException as e:
        duration = "API Error"  # Default duration in case of API failure
        logger.error("Failed to get directions from Google Maps API.", exc_info=True)

    # -----------------------------
    # Emit Real-Time Update via Socket.IO
    # -----------------------------
    # Send the updated location and duration to all connected clients
    socketio.emit('new_location', {
        'id': location.id,  # Unique identifier of the location
        'lat': location.latitude,  # Updated latitude
        'lon': location.longitude,  # Updated longitude
        'name': location.name,  # User's name
        'timestamp': location.timestamp.isoformat(),  # Timestamp in ISO format
        'duration': duration  # Duration from user to home
    })
    logger.info(f"Emitted new_location event for: {name} with duration: {duration}")
    
    # Respond to the client indicating success
    return {'status': 'success', 'duration': duration}

@app.route('/get_all_locations', methods=['GET'])
def get_all_locations():
    """
    Endpoint to retrieve all user locations from the database.
    Returns a JSON list of locations.
    """
    try:
        locations = Location.query.all()  # Query all location records
        data = [{
            'id': loc.id,  # Location ID
            'latitude': loc.latitude,  # Latitude
            'longitude': loc.longitude,  # Longitude
            'name': loc.name,  # User's name
            'timestamp': loc.timestamp.isoformat()  # Timestamp in ISO format
        } for loc in locations]
        logger.info(f"Fetched all locations: {len(data)} records.")
        return {'locations': data}  # Return the list of locations
    except Exception as e:
        logger.error("Failed to fetch all locations.", exc_info=True)
        return {'status': 'error', 'message': 'Failed to fetch locations.'}, 500  # Internal Server Error

@app.route('/get_latest_location', methods=['GET'])
def get_latest_location():
    """
    Endpoint to retrieve the latest user location from the database.
    Returns the most recent location entry.
    """
    try:
        latest_location = Location.query.order_by(Location.timestamp.desc()).first()  # Get the latest location
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
        return {'status': 'error', 'message': 'Failed to fetch the latest location.'}, 500  # Internal Server Error

@app.route('/send_notification', methods=['POST'])
def send_notification():
    """
    Endpoint to send a notification to a user via Pushover.
    Expects JSON data with 'name' and optionally 'message'.
    """
    data = request.json  # Parse JSON data from the request
    name = data.get('name')  # User's name to notify
    message = data.get('message', 'Live Location')  # Optional custom message, defaults to 'Live Location'

    # Validate that the 'name' field is present
    if name is None:
        logger.error("Name is required to send a notification.")
        return {'status': 'error', 'message': 'Name is required.'}, 400  # Bad Request

    # Fetch the latest location for the given name
    location = Location.query.filter_by(name=name).order_by(Location.timestamp.desc()).first()
    if location:
        # Construct the notification message with the user's current coordinates
        message = f"{name}'s current location: ({location.latitude}, {location.longitude})"
        logger.info(f"Sending notification for {name}: {message}")
    else:
        # Inform that no location data was found for the user
        message = f"No location data found for {name}."
        logger.warning(f"Attempted to send notification for nonexistent location: {name}")

    def send_pushover_notification(user_key, app_token, message):
        """
        Helper function to send a Pushover notification.
        """
        url = "https://api.pushover.net/1/messages.json"  # Pushover API endpoint
        data = {
            "token": app_token,  # Pushover application token
            "user": user_key,  # Pushover user key
            "message": message,  # Notification message
            "priority": "-1"  # Priority level (e.g., -1 for no alert)
        }
        try:
            response = requests.post(url, data=data)  # Send the POST request to Pushover
            response.raise_for_status()  # Raise an exception for HTTP error responses
            logger.info("Pushover notification sent successfully.")
        except requests.exceptions.RequestException as e:
            logger.error("Failed to send Pushover notification.", exc_info=True)

    # Pushover credentials
    # **Caution:** Replace these hardcoded credentials with environment variables for enhanced security
    USER_KEY = "updpmtd33jnw8jjweqm6f5p526aqam"  # Pushover user key
    APP_TOKEN = "azfqtfbaypgs7v863jt752gdu5y93e"  # Pushover application token

    # Send the notification using the helper function
    send_pushover_notification(USER_KEY, APP_TOKEN, message)
    return {'status': 'success'}  # Respond indicating success

# -----------------------------
# New Route: Get Route Polyline
# -----------------------------

@app.route('/get_route', methods=['GET'])
def get_route():
    """
    Endpoint to fetch the route polyline and duration from a user's location to home.
    Expects 'lat' and 'lon' as query parameters.
    """
    origin_lat = request.args.get('lat')  # Origin latitude from query parameters
    origin_lon = request.args.get('lon')  # Origin longitude from query parameters

    # Validate that both latitude and longitude are provided
    if not origin_lat or not origin_lon:
        logger.error("Origin coordinates are required.")
        return jsonify({'status': 'error', 'message': 'Origin coordinates are required.'}), 400  # Bad Request

    try:
        # Construct the origin string for the API request
        origin = f"{float(origin_lat)},{float(origin_lon)}"  # Ensure the coordinates are floats
    except ValueError:
        logger.error("Invalid origin coordinates.")
        return jsonify({'status': 'error', 'message': 'Invalid origin coordinates.'}), 400  # Bad Request

    # Construct the destination string using the predefined home coordinates
    destination = f"{DESTINATION_LAT},{DESTINATION_LON}"
    # Build the Google Maps Directions API URL with the origin, destination, and API key
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={GOOGLE_MAPS_API_KEY}"

    try:
        response = requests.get(url)  # Make the GET request to the Directions API
        response.raise_for_status()  # Raise an exception for HTTP error responses
        directions = response.json()  # Parse the JSON response

        # Check if the API response status is OK
        if directions['status'] != 'OK':
            logger.error(f"Directions API error: {directions['status']}")
            return jsonify({'status': 'error', 'message': 'Directions API error.', 'details': directions['status']}), 500  # Internal Server Error

        # Extract the encoded polyline and duration from the API response
        polyline_str = directions['routes'][0]['overview_polyline']['points']  # Encoded polyline for the route
        duration = directions['routes'][0]['legs'][0]['duration']['text']  # Duration text (e.g., "15 mins")
        logger.info(f"Fetched polyline for route from {origin} to home with duration {duration}.")
        return jsonify({'status': 'success', 'polyline': polyline_str, 'duration': duration})  # Successful response

    except requests.exceptions.RequestException as e:
        # Handle any exceptions that occur during the API request
        logger.error("Failed to fetch route from Google Maps Directions API.", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Failed to fetch route from Directions API.'}), 500  # Internal Server Error

# -----------------------------
# Main Entry Point
# -----------------------------

if __name__ == '__main__':
    # Run the Flask application with Socket.IO support
    # `allow_unsafe_werkzeug=True` allows Socket.IO to use the Werkzeug development server
    # **Caution:** In production, use a production-ready server like Gunicorn or uWSGI
    socketio.run(app, allow_unsafe_werkzeug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
