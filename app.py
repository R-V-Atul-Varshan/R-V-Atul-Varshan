import os
import uuid
import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)

# â”€â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///hazeapp.db"
).replace("postgres://", "postgresql://")          # Render uses postgres:// but SQLAlchemy needs postgresql://
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "hazeapp-secret-change-in-prod")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(days=7)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024   # 16 MB

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff"}

# â”€â”€â”€ Extensions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
db     = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt    = JWTManager(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# â”€â”€â”€ Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class User(db.Model):
    __tablename__ = "users"
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    images     = db.relationship("Image", backref="owner", lazy=True, cascade="all, delete")


class Image(db.Model):
    __tablename__ = "images"
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename      = db.Column(db.String(200), nullable=False)          # stored name (uuid)
    original_name = db.Column(db.String(200), nullable=False)          # original filename
    file_size     = db.Column(db.Integer, nullable=False)              # bytes
    mimetype      = db.Column(db.String(100), nullable=False)
    uploaded_at   = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    download_count= db.Column(db.Integer, default=0)
    last_download = db.Column(db.DateTime, nullable=True)


with app.app_context():
    db.create_all()

# â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def image_to_dict(img):
    return {
        "id":             img.id,
        "original_name":  img.original_name,
        "file_size":      img.file_size,
        "mimetype":       img.mimetype,
        "uploaded_at":    img.uploaded_at.isoformat(),
        "download_count": img.download_count,
        "last_download":  img.last_download.isoformat() if img.last_download else None,
    }

# â”€â”€â”€ Auth Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email    = (data.get("email")    or "").strip().lower()
    password =  data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user   = User(username=username, email=email, password=hashed)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "username": user.username, "email": user.email}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email")    or "").strip().lower()
    password =  data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "username": user.username, "email": user.email}), 200


@app.route("/api/me", methods=["GET"])
@jwt_required()
def me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"username": user.username, "email": user.email,
                    "created_at": user.created_at.isoformat()}), 200

# â”€â”€â”€ Image Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/upload", methods=["POST"])
@jwt_required()
def upload():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Use PNG, JPG, GIF, WEBP, BMP, or TIFF"}), 400

    ext           = file.filename.rsplit(".", 1)[1].lower()
    stored_name   = f"{uuid.uuid4()}.{ext}"
    save_path     = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)
    file.save(save_path)
    file_size     = os.path.getsize(save_path)

    img = Image(
        user_id       = int(get_jwt_identity()),
        filename      = stored_name,
        original_name = secure_filename(file.filename),
        file_size     = file_size,
        mimetype      = file.mimetype or f"image/{ext}",
    )
    db.session.add(img)
    db.session.commit()

    return jsonify({"message": "Upload successful", "image": image_to_dict(img)}), 201


@app.route("/api/download/<int:image_id>", methods=["GET"])
@jwt_required()
def download(image_id):
    user_id = int(get_jwt_identity())
    img     = Image.query.filter_by(id=image_id, user_id=user_id).first()
    if not img:
        return jsonify({"error": "Image not found or access denied"}), 404

    img.download_count += 1
    img.last_download   = datetime.datetime.utcnow()
    db.session.commit()

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        img.filename,
        as_attachment=True,
        download_name=img.original_name
    )


@app.route("/api/history", methods=["GET"])
@jwt_required()
def history():
    user_id = int(get_jwt_identity())
    page    = request.args.get("page",  1,  type=int)
    per_page= request.args.get("limit", 10, type=int)
    per_page= min(per_page, 50)

    pagination = (Image.query
                  .filter_by(user_id=user_id)
                  .order_by(Image.uploaded_at.desc())
                  .paginate(page=page, per_page=per_page, error_out=False))

    return jsonify({
        "images":      [image_to_dict(i) for i in pagination.items],
        "total":       pagination.total,
        "page":        pagination.page,
        "total_pages": pagination.pages,
        "has_next":    pagination.has_next,
        "has_prev":    pagination.has_prev,
    }), 200


@app.route("/api/image/<int:image_id>", methods=["DELETE"])
@jwt_required()
def delete_image(image_id):
    user_id = int(get_jwt_identity())
    img     = Image.query.filter_by(id=image_id, user_id=user_id).first()
    if not img:
        return jsonify({"error": "Image not found or access denied"}), 404

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], img.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(img)
    db.session.commit()
    return jsonify({"message": "Image deleted"}), 200


@app.route("/api/stats", methods=["GET"])
@jwt_required()
def stats():
    user_id     = int(get_jwt_identity())
    images      = Image.query.filter_by(user_id=user_id).all()
    total_up    = len(images)
    total_dl    = sum(i.download_count for i in images)
    total_size  = sum(i.file_size for i in images)
    return jsonify({
        "total_uploads":   total_up,
        "total_downloads": total_dl,
        "total_size_bytes": total_size,
    }), 200


# â”€â”€â”€ Health check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "HazeApp API"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
