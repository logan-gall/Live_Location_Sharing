from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit
import os
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

GOOGLE_MAPS_API_KEY = "AIzaSyBIZt7GRemJ5z5zRcXMDks7hi3GvXXiwKI"
DESTINATION_LAT = 44.987303
DESTINATION_LON = -93.221375


@app.route('/')
def index():
    return render_template('index.html')  # The HTML file with Leaflet and Socket.IO

@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.json
    print(data)
    
    with open('latest_location.txt', 'w') as f:
        f.write(f"{data['latitude']},{data['longitude']}")

    # Call Google Maps Directions API
    origin = f"{data['latitude']},{data['longitude']}"
    destination = f"{DESTINATION_LAT},{DESTINATION_LON}"
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={GOOGLE_MAPS_API_KEY}"
    
    response = requests.get(url)
    if response.status_code == 200:
        directions = response.json()
        duration = directions['routes'][0]['legs'][0]['duration']['text']
        
        # Emit the new location and duration
        socketio.emit('new_location', {'lat': data['latitude'], 'lon': data['longitude'], 'duration': duration})
        
        return {'status': 'success', 'duration': duration}
    else:
        return {'status': 'error', 'message': 'Failed to get directions'}

@app.route('/get_latest_location', methods=['GET'])
def get_latest_location():
    try:
        with open('latest_location.txt', 'r') as f:
            lat, lon = f.read().split(',')
            return {'latitude': lat, 'longitude': lon}
    except FileNotFoundError:
        # Return a default location if the file does not exist
        return {'latitude': '0', 'longitude': '0'}

@app.route('/send_notification', methods=['POST'])
def send_notification():
    def send_pushover_notification(user_key, app_token, message):
        url = "https://api.pushover.net/1/messages.json"
        data = {
            "token": app_token,
            "user": user_key,
            "message": message,
            "priority":"-1"
        }
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("Notification sent successfully.")
        else:
            print(f"Failed to send notification. Status code: {response.status_code}")

    # Replace these with your Pushover User Key and API Token
    USER_KEY = "updpmtd33jnw8jjweqm6f5p526aqam"
    APP_TOKEN = "azfqtfbaypgs7v863jt752gdu5y93e"
    MESSAGE = "Live Location"
    # Your script's main logic here

    # After the task is done
    send_pushover_notification(USER_KEY, APP_TOKEN, MESSAGE)
    return {'status': 'success'}

# File to store recipes
RECIPE_FILE = 'recipes.txt'

# Function to load recipes from file
def load_recipes():
    recipes = []
    try:
        with open(RECIPE_FILE, 'r') as file:
            for line in file:
                try:
                    title, ingredients, instructions, calories = line.strip().split('|')
                    ingredients = ingredients.replace('\\n', '\n')
                    instructions = instructions.replace('\\n', '\n')
                    calories = calories.replace('\\n', '\n')
                    recipes.append({'title': title, 'ingredients': ingredients, 'instructions': instructions, 'calories': calories})
                except Exception as e:
                    print('error on line: ' + line)
    except FileNotFoundError:
        pass
    return recipes

# Function to save a recipe to file
def save_recipe(title, ingredients, instructions, calories):
    ingredients = ingredients.replace('\n', '\\n')
    ingredients = ingredients.replace('\r', '')
    instructions = instructions.replace('\n', '\\n')
    instructions = instructions.replace('\r', '')
    calories = calories.replace('\n', '\\n')
    calories = calories.replace('\r', '')
    with open(RECIPE_FILE, 'a') as file:
        file.write(f'{title}|{ingredients}|{instructions}|{calories}\n')

@app.route('/recipes')
def recipes():
    recipes = load_recipes()
    return render_template('recipes.html', recipes=recipes)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        title = request.form['title']
        ingredients = request.form['ingredients']
        instructions = request.form['instructions']
        calories = request.form['calories']
        save_recipe(title, ingredients, instructions, calories)
        return redirect(url_for('recipes'))
    return render_template('add.html')

@app.route('/recipes.txt')
def recipes_txt():
    try:
        with open(RECIPE_FILE, 'r') as file:
            content = file.read()
        return content, 200, {'Content-Type': 'text/plain'}
    except FileNotFoundError:
        return "No recipes found.", 404, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
