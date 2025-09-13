# First, ensure you have the necessary libraries installed:
# pip install Flask werkzeug httpx

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import httpx  # Used for making async API calls

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['USER_DB'] = 'users.json'

# ----------------------
# Gemini AI Model Integration
# ----------------------
# Note: No local model loading is needed anymore.

async def generate_ai_response(user_message):
    """Generate AI chat response using the Gemini API"""
    # You can leave the API key empty if running in a supported environment
    api_key = "AIzaSyCaTvzA-TJ3laNGz2O4SZM-tDXqkk0cbw0" 
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"

    # Construct the chat history payload for the API
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "You are HealthAI, a helpful and responsible AI assistant."}]
            },
            {
                "role": "model",
                "parts": [{"text": "Understood. I am HealthAI. How can I help?"}]
            },
            {
                "role": "user",
                "parts": [{"text": user_message}]
            }
        ]
    }

    try:
        # Use httpx for an asynchronous POST request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            result = response.json()

            # Safely extract the text from the response
            if (result.get('candidates') and 
                result['candidates'][0].get('content') and 
                result['candidates'][0]['content'].get('parts')):
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                return "I'm sorry, I couldn't generate a response at the moment."

    except httpx.RequestError as e:
        print(f"An error occurred while requesting from Gemini API: {e}")
        return "Error: Could not connect to the AI service."
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return "An unexpected error occurred while generating the response."

# ----------------------
# User DB Helpers
# ----------------------
def init_user_db():
    if not os.path.exists(app.config['USER_DB']):
        with open(app.config['USER_DB'], 'w') as f:
            json.dump([], f)

def get_users():
    init_user_db()
    with open(app.config['USER_DB'], 'r') as f:
        return json.load(f)

def save_users(users):
    with open(app.config['USER_DB'], 'w') as f:
        json.dump(users, f, indent=2)

def find_user(email):
    for user in get_users():
        if user['email'] == email:
            return user
    return None

def register_user(email, password, first_name, last_name):
    if find_user(email):
        return False, "Email already registered"
    users = get_users()
    users.append({
        'email': email,
        'password': generate_password_hash(password),
        'first_name': first_name,
        'last_name': last_name,
        'created_at': datetime.now().isoformat()
    })
    save_users(users)
    return True, ""

def verify_user(email, password):
    user = find_user(email)
    if not user:
        return False, "User not found"
    if not check_password_hash(user['password'], password):
        return False, "Incorrect password"
    return True, user

# ----------------------
# Routes
# ----------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        success, result = verify_user(email, password)
        if success:
            session['user'] = {
                'email': email,
                'first_name': result['first_name'],
                'last_name': result['last_name']
            }
            return redirect(url_for('dashboard'))
        else:
            error = result
    return render_template('login.html', error=error)

@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    success, message = register_user(email, password, first_name, last_name)
    if success:
        session['user'] = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name
        }
        return redirect(url_for('dashboard'))
    return render_template('login.html', signup_error=message, show_signup=True)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

# ----------------------
# Chat API Endpoints
# ----------------------
@app.route('/send_message', methods=['POST'])
async def send_message():  # Route is now async
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    user_message = data.get("message", "")
    if not user_message.strip():
        return jsonify({"error": "Message cannot be empty"}), 400
    
    # Await the async function call
    ai_reply = await generate_ai_response(user_message)
    return jsonify({"reply": ai_reply})

@app.route('/feedback', methods=['POST'])
def feedback():
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    sentiment = data.get("sentiment")
    concern = data.get("concern")
    feedback_entry = {
        "user": session['user']['email'],
        "sentiment": sentiment,
        "concern": concern,
        "timestamp": datetime.now().isoformat()
    }
    with open("feedback.json", "a") as f:
        f.write(json.dumps(feedback_entry) + "\n")
    return jsonify({"status": "Feedback received"})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
