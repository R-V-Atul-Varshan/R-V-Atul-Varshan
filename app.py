from flask import Flask, request, jsonify, send_from_directory
import os
import sqlite3
import cv2
import numpy as np
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
DB = "database.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# -----------------------
# DATABASE INIT
# -----------------------

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        original TEXT,
        output TEXT,
        date TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -----------------------
# IMAGE DEHAZE FUNCTION
# -----------------------

def dehaze(image):

    img = image.astype(np.float32) / 255

    dark = np.min(img, axis=2)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15,15))
    dark = cv2.erode(dark, kernel)

    A = np.max(img)

    t = 1 - 0.95 * dark
    t = np.clip(t,0.1,1)

    J = np.zeros_like(img)

    for i in range(3):
        J[:,:,i] = (img[:,:,i] - A) / t + A

    J = np.clip(J,0,1)

    result = (J*255).astype(np.uint8)

    return result


# -----------------------
# SIGNUP
# -----------------------

@app.route("/signup", methods=["POST"])
def signup():

    data = request.json
    username = data["username"]
    password = data["password"]

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    try:
        c.execute("INSERT INTO users(username,password) VALUES(?,?)",(username,password))
        conn.commit()
        msg = "Signup successful"
    except:
        msg = "User already exists"

    conn.close()

    return jsonify({"message":msg})


# -----------------------
# LOGIN
# -----------------------

@app.route("/login", methods=["POST"])
def login():

    data = request.json
    username = data["username"]
    password = data["password"]

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    user = c.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username,password)
    ).fetchone()

    conn.close()

    if user:
        return jsonify({"message":"Login success"})
    else:
        return jsonify({"message":"Invalid login"}),401


# -----------------------
# IMAGE UPLOAD + DEHAZE
# -----------------------

@app.route("/upload", methods=["POST"])
def upload():

    username = request.form["username"]
    file = request.files["image"]

    original_name = file.filename
    upload_path = os.path.join(UPLOAD_FOLDER, original_name)

    file.save(upload_path)

    img = cv2.imread(upload_path)

    result = dehaze(img)

    output_name = "dehazed_" + original_name
    output_path = os.path.join(OUTPUT_FOLDER, output_name)

    cv2.imwrite(output_path, result)

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "INSERT INTO history(username,original,output,date) VALUES(?,?,?,?)",
        (username, original_name, output_name, str(datetime.now()))
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message":"Image processed",
        "download":"/download/"+output_name
    })


# -----------------------
# DOWNLOAD IMAGE
# -----------------------

@app.route("/download/<filename>")
def download(filename):

    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)


# -----------------------
# USER HISTORY
# -----------------------

@app.route("/history/<username>")
def history(username):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    rows = c.execute(
        "SELECT original,output,date FROM history WHERE username=?",
        (username,)
    ).fetchall()

    conn.close()

    history = []

    for r in rows:
        history.append({
            "original":r[0],
            "output":r[1],
            "date":r[2],
            "download":"/download/"+r[1]
        })

    return jsonify(history)


# -----------------------
# RUN SERVER
# -----------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
