from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import cv2
import numpy as np

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE = "database.db"


# -----------------------
# DATABASE INIT
# -----------------------

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


# -----------------------
# HAZE REMOVAL FUNCTION
# -----------------------

def remove_haze(image_path):

    img = cv2.imread(image_path)

    # convert to LAB color space
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # CLAHE improves contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    cl = clahe.apply(l)

    merged = cv2.merge((cl,a,b))
    enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    # additional sharpening
    kernel = np.array([[0,-1,0],
                       [-1,5,-1],
                       [0,-1,0]])

    sharpened = cv2.filter2D(enhanced,-1,kernel)

    return sharpened


# -----------------------
# SIGNUP
# -----------------------

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
        (username,email,password)
    )

    conn.commit()
    conn.close()

    return jsonify({"message":"Signup success"})


# -----------------------
# LOGIN
# -----------------------

@app.route("/login", methods=["POST"])
def login():

    data = request.json

    email = data.get("email")
    password = data.get("password")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute(
        "SELECT id FROM users WHERE email=? AND password=?",
        (email,password)
    )

    user = c.fetchone()

    conn.close()

    if user:
        return jsonify({"user_id":user[0]})
    else:
        return jsonify({"error":"Invalid login"})


# -----------------------
# UPLOAD IMAGE
# -----------------------

@app.route("/upload", methods=["POST"])
def upload():

    file = request.files["image"]
    user_id = request.form["user_id"]

    filepath = os.path.join(UPLOAD_FOLDER,file.filename)

    file.save(filepath)

    # haze removal
    result = remove_haze(filepath)

    cv2.imwrite(filepath,result)

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute(
        "INSERT INTO history(user_id,filename) VALUES(?,?)",
        (user_id,file.filename)
    )

    conn.commit()
    conn.close()

    return jsonify({"file":file.filename})


# -----------------------
# HISTORY
# -----------------------

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


# -----------------------
# DOWNLOAD
# -----------------------

@app.route("/download/<filename>")
def download(filename):

    return send_from_directory(UPLOAD_FOLDER,filename)


# -----------------------
# RUN
# -----------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000,debug=True)
