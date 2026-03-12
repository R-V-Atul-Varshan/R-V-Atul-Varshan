from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import cv2

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE = "database.db"


# ------------------------
# DATABASE INITIALIZATION
# ------------------------

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ------------------------
# SIGNUP
# ------------------------

@app.route("/signup", methods=["POST"])
def signup():

    data = request.json
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute(
        "INSERT INTO users(username,email,password) VALUES(?,?,?)",
        (username, email, password)
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Signup successful"})


# ------------------------
# LOGIN
# ------------------------

@app.route("/login", methods=["POST"])
def login():

    data = request.json
    email = data.get("email")
    password = data.get("password")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute(
        "SELECT id FROM users WHERE email=? AND password=?",
        (email, password)
    )

    user = c.fetchone()

    conn.close()

    if user:
        return jsonify({"user_id": user[0]})
    else:
        return jsonify({"error": "Invalid credentials"})


# ------------------------
# UPLOAD IMAGE
# ------------------------

@app.route("/upload", methods=["POST"])
def upload():

    file = request.files["image"]
    user_id = request.form["user_id"]

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    # Simple image enhancement (simulate dehazing)
    img = cv2.imread(filepath)
    enhanced = cv2.convertScaleAbs(img, alpha=1.4, beta=25)
    cv2.imwrite(filepath, enhanced)

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute(
        "INSERT INTO history(user_id, filename) VALUES(?,?)",
        (user_id, file.filename)
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Image uploaded", "file": file.filename})


# ------------------------
# USER HISTORY
# ------------------------

@app.route("/history/<user_id>")
def history(user_id):

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute(
        "SELECT filename FROM history WHERE user_id=?",
        (user_id,)
    )

    rows = c.fetchall()
    conn.close()

    files = [r[0] for r in rows]

    return jsonify(files)


# ------------------------
# DOWNLOAD IMAGE
# ------------------------

@app.route("/download/<filename>")
def download(filename):

    return send_from_directory(UPLOAD_FOLDER, filename)


# ------------------------
# RUN SERVER
# ------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
