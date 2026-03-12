from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import cv2
import numpy as np
import os
import uuid

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
DB = "database.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)


# --------------------------
# DATABASE INIT
# --------------------------

def init_db():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        original TEXT,
        result TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# --------------------------
# IMAGE DEHAZE
# --------------------------

def dehaze(img):

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

    l,a,b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=3.0)

    cl = clahe.apply(l)

    merged = cv2.merge((cl,a,b))

    result = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    return result


# --------------------------
# SIGNUP
# --------------------------

@app.route("/signup", methods=["POST"])
def signup():

    data = request.json

    username = data["username"]
    password = data["password"]

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("INSERT INTO users(username,password) VALUES(?,?)",
              (username,password))

    conn.commit()
    conn.close()

    return jsonify({"msg":"Signup success"})


# --------------------------
# LOGIN
# --------------------------

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
        return jsonify({"msg":"Login success"})
    else:
        return jsonify({"msg":"Invalid credentials"})


# --------------------------
# UPLOAD + DEHAZE
# --------------------------

@app.route("/upload", methods=["POST"])
def upload():

    username = request.form["username"]
    file = request.files["image"]

    uid = str(uuid.uuid4())

    original_path = f"{UPLOAD_FOLDER}/{uid}.jpg"
    result_path = f"{RESULT_FOLDER}/{uid}.jpg"

    file.save(original_path)

    img = cv2.imread(original_path)

    result = dehaze(img)

    cv2.imwrite(result_path,result)

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "INSERT INTO history(username,original,result) VALUES(?,?,?)",
        (username,original_path,result_path)
    )

    conn.commit()
    conn.close()

    return send_file(result_path, mimetype="image/jpeg")


# --------------------------
# USER HISTORY
# --------------------------

@app.route("/history/<username>")
def history(username):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    rows = c.execute(
        "SELECT result FROM history WHERE username=?",
        (username,)
    ).fetchall()

    conn.close()

    images = [r[0] for r in rows]

    return jsonify(images)


# --------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
