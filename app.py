from flask import Flask, render_template, request, redirect, send_from_directory, url_for, session, jsonify
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database.mongo_connection import MongoDBConnection
from models.user_model import User
from models import hf_classifier
import os
import datetime
from rembg import remove
from PIL import Image
import io

# Function to remove background and resize image
from PIL import Image, ImageOps

app = Flask(
    __name__,
    template_folder='assets/templates',
    static_folder='assets/static'
)
app.secret_key = 'supersecretkey'
OPENWEATHER_API_KEY = 'e7f6a61398d961be542c9f01ded592aa'

# Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'assets', 'uploads')
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# MongoDB connection
mongo_conn = MongoDBConnection()

@app.route('/')
def homepage():
    return render_template('homepage.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        preferences = request.form.getlist('preferences')
        city = request.form['city']
        country = request.form['country']

        # Check if user exists
        if mongo_conn.get_user(username):
            return "User already exists!"

        # Register user with location
        user = User(
            username=username,
            password=password,
            preferences=preferences,
            city=city,
            country=country
        )
        mongo_conn.register_user(user)
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = mongo_conn.get_user(username)
        if user and check_password_hash(user['password'], password):
            session['user'] = username
            return redirect(url_for('dashboard'))
        return "Invalid username or password!"

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session['user'])

@app.route('/wardrobe')
def view_wardrobe():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('my_wardrobe.html')
@app.route('/wardrobe_data', methods=["GET"])
def fetch_wardrobe_data():
    if 'user' not in session:
        return jsonify({"error": "User not logged in"}), 403

    user_id = session['user']
    wardrobe_items = mongo_conn.get_user_wardrobe(user_id)

    grouped_items = {}
    for item in wardrobe_items:
        category = item.get("classification", {}).get("category", "Unknown")
        item["_id"] = str(item["_id"])
        grouped_items.setdefault(category, []).append(item)

    return jsonify(grouped_items)





def process_image(image_path):
    try:
        # Open the image file
        with open(image_path, "rb") as image_file:
            input_image = image_file.read()

        # Remove background
        output_image = remove(input_image)

        # Convert to Pillow image
        image = Image.open(io.BytesIO(output_image)).convert("RGBA")

        # Resize to a uniform dimension
        uniform_size = (400, 400)
        image = image.resize(uniform_size, Image.Resampling.LANCZOS)

        # Add a white background if needed (optional, for better display)
        background = Image.new("RGBA", uniform_size, (255, 255, 255, 255))
        background.paste(image, (0, 0), image)

        # Save the processed image back
        background.save(image_path, format="PNG")
    except Exception as e:
        print(f"Error in process_image: {str(e)}")

@app.route('/update_location', methods=['POST'])
def update_location():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    city = request.form.get('city')
    country = request.form.get('country')
    
    if not city or not country:
        return "City and country are required!", 400
    
    # Update user location in database
    mongo_conn.update_user_location(session['user'], city, country)
    
    return redirect(url_for('profile'))
@app.route('/upload_item', methods=["POST"])
def upload_wardrobe_item():
    try:
        if 'user' not in session:
            return jsonify({"error": "Unauthorized access"}), 403

        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({"error": "No file uploaded"}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Process the image (remove background and resize)
        process_image(filepath)

        # Classify the image
        classification_result = hf_classifier.classify_image(filepath)

        # Store wardrobe item
        wardrobe_item = {
            "filename": filename,
            "image_path": url_for('uploaded_file', filename=filename),
            "user_id": session['user'],
            "upload_date": datetime.datetime.now().isoformat(),
            "classification": classification_result,
        }

        # Insert into MongoDB and get the inserted ID
        inserted_id = mongo_conn.insert_wardrobe_item(session['user'], wardrobe_item)

        # Add the string version of the ObjectId to the wardrobe_item
        wardrobe_item["_id"] = str(inserted_id)

        return jsonify({"message": "Item uploaded successfully", "item": wardrobe_item})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"An error occurred while uploading the item: {str(e)}"}), 500

# Serve images from the uploads directory
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/recommendations')
def recommendations():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']
    wardrobe_items = mongo_conn.get_user_wardrobe(user_id)

    # Add logic for generating recommendations based on uploaded items
    recommendations = []  # Placeholder
    return render_template('recommendations.html', recommendations=recommendations)
def get_weather(city, country):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city},{country}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            return {
                'temperature': data['main']['temp'],
                'condition': data['weather'][0]['main'],
                'humidity': data['main']['humidity'],
                'city': city
            }
        return None
    except Exception as e:
        print(f"Error fetching weather: {str(e)}")
        return None

import datetime

def get_weather_based_recommendations(weather, wardrobe_items):
    # Get current timestamp for 12-hour rotation
    current_time = datetime.datetime.now()
    rotation_period = current_time.replace(hour=current_time.hour - (current_time.hour % 12), 
                                         minute=0, second=0, microsecond=0)
    # Create a seed for consistent but rotating selection
    rotation_seed = int(rotation_period.timestamp() / (12 * 3600))  # Changes every 12 hours
    
    temp = weather['temperature']
    condition = weather['condition'].lower()
    
    # Define clothing categories for different weather conditions
    WARM_TOPS = ['Sweater', 'Turtleneck', 'Flannel', 'Henley']
    LIGHT_TOPS = ['Tee', 'Tank', 'Blouse', 'Top', 'Button-Down', 'Halter']
    WARM_OUTERWEAR = ['Coat', 'Peacoat', 'Parka', 'Bomber', 'Hoodie']
    LIGHT_OUTERWEAR = ['Blazer', 'Cardigan', 'Kimono']
    RAIN_GEAR = ['Anorak', 'Jacket']
    WARM_BOTTOMS = ['Jeans', 'Sweatpants', 'Joggers']
    LIGHT_BOTTOMS = ['Shorts', 'Skirt', 'Culottes', 'Capris']
    FULL_BODY = ['Dress', 'Jumpsuit', 'Romper']
    
    recommendations = []
    weather_note = ""
    required_categories = []

    # Temperature-based recommendations
    if temp < 10:  # Very Cold (Below 10°C)
        weather_note = "It's very cold! Layer up with warm clothing."
        required_categories = [
            ('warm_top', WARM_TOPS, "a warm top"),
            ('warm_outerwear', WARM_OUTERWEAR, "a warm outer layer"),
            ('warm_bottom', WARM_BOTTOMS, "warm bottoms")
        ]
        
    elif 10 <= temp < 18:  # Cool (10-18°C)
        weather_note = "Cool weather - perfect for light layering."
        required_categories = [
            ('light_top', LIGHT_TOPS, "a light top"),
            ('light_outerwear', LIGHT_OUTERWEAR + WARM_OUTERWEAR, "a light jacket or cardigan"),
            ('bottom', WARM_BOTTOMS, "comfortable bottoms")
        ]
        
    elif 18 <= temp < 25:  # Moderate (18-25°C)
        weather_note = "Pleasant temperature - great for most clothing options."
        required_categories = [
            ('top', LIGHT_TOPS, "a comfortable top"),
            ('bottom', LIGHT_BOTTOMS + WARM_BOTTOMS, "suitable bottoms"),
            ('optional_layer', LIGHT_OUTERWEAR, "a light layer for evening")
        ]
        
    else:  # Hot (25°C and above)
        weather_note = "Hot weather - choose light, breathable clothing."
        required_categories = [
            ('light_top', LIGHT_TOPS, "a breathable top"),
            ('light_bottom', LIGHT_BOTTOMS, "light bottoms")
        ]
        # Add option for full-body items in hot weather
        if any(item['classification']['label'] in FULL_BODY for item in wardrobe_items):
            required_categories.append(('full_body', FULL_BODY, "a breezy dress or romper"))

    # Weather condition modifiers
    if 'rain' in condition or 'drizzle' in condition:
        weather_note += " Don't forget rain protection!"
        required_categories.insert(0, ('rain_gear', RAIN_GEAR, "rain protection"))
    elif 'snow' in condition:
        weather_note += " Snowfall expected - prioritize warm, waterproof layers!"
        required_categories.insert(0, ('warm_outerwear', WARM_OUTERWEAR, "a warm, protective coat"))
    elif 'thunderstorm' in condition:
        weather_note += " Stormy conditions - bring weatherproof outerwear!"
        required_categories.insert(0, ('rain_gear', RAIN_GEAR, "waterproof protection"))
    elif 'cloudy' in condition and temp < 20:
        weather_note += " Cloudy and cool - an extra layer might be nice."
        if not any(cat[0] == 'light_outerwear' for cat in required_categories):
            required_categories.append(('light_outerwear', LIGHT_OUTERWEAR, "a light layer"))

    # Find matching items from wardrobe with rotation
    selected_items = []
    missing_items = []

    for category_type, category_options, category_description in required_categories:
        matching_items = [
            item for item in wardrobe_items 
            if item['classification']['label'] in category_options
        ]
        
        if matching_items:
            # Sort items to ensure consistent ordering
            matching_items.sort(key=lambda x: x['classification']['label'])
            
            # Use rotation seed to select different items every 12 hours
            selection_index = (rotation_seed + len(selected_items)) % len(matching_items)
            selected_items.append(matching_items[selection_index])
        else:
            missing_items.append(category_description)

    # Update weather note with missing items
    if missing_items:
        weather_note += f"\nConsider adding {', '.join(missing_items)} to your wardrobe for this weather."

    # Add time period to weather note
    period = "morning to afternoon" if current_time.hour < 12 else "evening to night"
    weather_note = f"{weather_note}"

    return {
        'items': selected_items,
        'weatherNote': weather_note,
        'missing': missing_items,
        'rotationPeriod': rotation_period.strftime("%Y-%m-%d %H:00"),
        'nextRotation': (rotation_period + datetime.timedelta(hours=12)).strftime("%Y-%m-%d %H:00")
    }
@app.route('/weather_recommendations')
def weather_recommendations():
    if 'user' not in session:
        return jsonify({"error": "User not logged in"}), 403
    
    user = mongo_conn.get_user(session['user'])
    
    # Check if user has location information
    if not user.get('city') or not user.get('country'):
        return jsonify({
            "error": "Location not set",
            "message": "Please update your location in your profile"
        }), 400
    
    weather = get_weather(user['city'], user['country'])
    
    if not weather:
        return jsonify({"error": "Unable to fetch weather data"}), 500
    
    wardrobe_items = mongo_conn.get_user_wardrobe(session['user'])
    recommendations = get_weather_based_recommendations(weather, wardrobe_items)
    
    return jsonify({
        "weather": weather,
        "recommendations": recommendations
    })
    
@app.route('/tryon')
def tryon():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('tryon.html')

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = mongo_conn.get_user(session['user'])
    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('homepage'))

if __name__ == '__main__':
    app.run(debug=True)