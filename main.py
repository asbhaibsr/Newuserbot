import os
from flask import Flask, request, jsonify
from pymongo import MongoClient

# --- Configuration (Koyeb Environment Variables se aayenge) ---
MONGO_URI = os.environ.get('MONGO_URI')

# --- MongoDB Setup (Health Check ke liye) ---
client_mongo = None
try:
    client_mongo = MongoClient(MONGO_URI)
    print("MongoDB client for Flask health check initialized.")
except Exception as e:
    print(f"MongoDB client initialization failed in Flask: {e}")
    # Flask app should still start even if DB connection fails initially

# --- Flask App for Monitoring (Port 8080) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Userbot is running! Visit /health for status."

@app.route('/health')
def health_check():
    db_status = "Disconnected"
    try:
        if client_mongo:
            client_mongo.admin.command('ping')
            db_status = "Connected"
        else:
            db_status = "Client Not Initialized" # Fallback if client_mongo failed init
    except Exception:
        db_status = "Disconnected"
    
    # Ye Flask app ka health status hai. Bot worker ka status alag se check nahi hoga.
    return jsonify(status="ok", web_server="running", db=db_status, timestamp=datetime.utcnow().isoformat())

# Ye block sirf local testing ke liye hai, Koyeb gunicorn se chalayega
if __name__ == '__main__':
    # Is block mein koi userbot ya async code nahi hona chahiye
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080))
