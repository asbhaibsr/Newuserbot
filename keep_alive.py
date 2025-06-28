import os
from flask import Flask
from threading import Thread # Flask को एक अलग थ्रेड में चलाने के लिए

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello! This is the keepalive web server. Userbot is running in main.py."

def run_flask_app():
    # Flask को 0.0.0.0 पर port 8080 पर चलाओ
    # ये Koyeb के health check के लिए है
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    print("Starting keep_alive.py Flask app...")
    # Flask app को एक अलग थ्रेड में चलाएं ताकि यह मुख्य प्रोसेस को ब्लॉक न करे (हालांकि, Procfile में अलग-अलग प्रोसेस ही बेहतर है)
    # Koyeb Procfile में अलग-अलग प्रोसेस के लिए इसे सीधे रन करने की जरूरत नहीं
    run_flask_app()
