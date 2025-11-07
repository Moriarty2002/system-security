import os
import datetime
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger
import jwt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, 'storage')

app = Flask(__name__)
CORS(app)

# Database configuration: prefer explicit DATABASE_URL (e.g. PostgreSQL).
# For easier local testing when DATABASE_URL is not set, fall back to a file-based SQLite DB.
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # sqlite file next to this script
    sqlite_path = os.path.join(BASE_DIR, 'homework.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{sqlite_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
db.init_app(app)


class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(128), primary_key=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    quota = db.Column(BigInteger, nullable=False, default=0)
    password_hash = db.Column(db.String(256), nullable=False)


def ensure_environment():
    os.makedirs(STORAGE_DIR, exist_ok=True)
    # Ensure DB tables and seed default users
    with app.app_context():
        db.create_all()
        admin = User.query.get('admin')
        if not admin:
            # seed admin and a staging user with hashed passwords
            # Defaults are intentionally simple for local testing; override with env vars in production.
            admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin')
            alice_pass = os.environ.get('ALICE_PASSWORD', 'alice')
            admin = User(username='admin', is_admin=True, quota=10 * 1024 * 1024 * 1024,
                         password_hash=generate_password_hash(admin_pass))
            alice = User(username='alice', is_admin=False, quota=100 * 1024 * 1024,
                         password_hash=generate_password_hash(alice_pass))
            db.session.add(admin)
            db.session.add(alice)
            db.session.commit()

            # create sample storage for alice so login and file listing can be tested immediately
            alice_dir = os.path.join(STORAGE_DIR, 'alice')
            try:
                os.makedirs(alice_dir, exist_ok=True)
                sample_path = os.path.join(alice_dir, 'welcome.txt')
                if not os.path.exists(sample_path):
                    with open(sample_path, 'w', encoding='utf-8') as fh:
                        fh.write('Hello alice! This is a sample file for testing.\n')
            except Exception:
                # non-fatal; storage is optional
                pass


def current_user():
    """Authenticate request using Bearer JWT in Authorization header.

    Falls back to X-User header only for quick local testing (not recommended).
    """
    auth = request.headers.get('Authorization')
    token = None
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1].strip()

    if token:
        try:
            payload = jwt.decode(token, os.environ.get('SECRET_KEY', 'dev-secret-key'), algorithms=['HS256'])
            username = payload.get('sub')
        except jwt.ExpiredSignatureError:
            abort(401, description='token expired')
        except Exception:
            abort(401, description='invalid token')
    else:
        # fallback - NOT secure, only for local/demo convenience
        username = request.headers.get('X-User')

    if not username:
        abort(401, description='Missing authentication')

    with app.app_context():
        user = User.query.get(username)
        if not user:
            abort(403, description='Unknown user')
        return username, user


def create_token(username, is_admin, expires_in=3600):
    secret = os.environ.get('SECRET_KEY', 'dev-secret-key')
    exp = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    payload = {'sub': username, 'is_admin': bool(is_admin), 'exp': exp}
    return jwt.encode(payload, secret, algorithm='HS256')


def user_usage_bytes(username):
    user_dir = os.path.join(STORAGE_DIR, username)
    total = 0
    if not os.path.exists(user_dir):
        return 0
    for root, dirs, files in os.walk(user_dir):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def user_files_list(username):
    user_dir = os.path.join(STORAGE_DIR, username)
    files = []
    if not os.path.exists(user_dir):
        return files
    for name in os.listdir(user_dir):
        path = os.path.join(user_dir, name)
        if os.path.isfile(path):
            stat = os.stat(path)
            files.append({
                'name': name,
                'size': stat.st_size,
                'mtime': int(stat.st_mtime)
            })
    return files


@app.before_request
def init():
    ensure_environment()


# ---- User endpoints ----
@app.route('/upload', methods=['POST'])
def upload_file():
    username, meta = current_user()

    if 'file' not in request.files:
        return jsonify({'error': 'no file part'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'no selected file'}), 400

    filename = secure_filename(f.filename)
    user_dir = os.path.join(STORAGE_DIR, username)
    os.makedirs(user_dir, exist_ok=True)

    # Compute file size
    file_stream = f.stream
    file_stream.seek(0, os.SEEK_END)
    file_size = file_stream.tell()
    file_stream.seek(0)

    # Lock the user row and check quota inside a transaction
    with app.app_context():
        # Acquire a FOR UPDATE lock to avoid concurrent quota races
        user = db.session.query(User).with_for_update().get(username)
        if not user:
            abort(403, description='Unknown user')
        current_usage = user_usage_bytes(username)
        if current_usage + file_size > (user.quota or 0):
            return jsonify({'error': 'quota exceeded'}), 403

        # Save file and commit (file system + DB are not strictly transactional here, but adequate for this simulation)
        save_path = os.path.join(user_dir, filename)
        f.save(save_path)
        # No DB metadata to update for file uploads; commit to release locks
        db.session.commit()

    return jsonify({'status': 'ok', 'filename': filename, 'size': file_size})


@app.route('/files', methods=['GET'])
def list_files():
    username, meta = current_user()
    files = user_files_list(username)
    usage = user_usage_bytes(username)
    return jsonify({'files': files, 'usage': usage, 'quota': meta.quota})


@app.route('/files/<path:filename>', methods=['GET'])
def download_file(filename):
    username, meta = current_user()
    user_dir = os.path.join(STORAGE_DIR, username)
    # prevent path traversal by using send_from_directory
    if not os.path.exists(os.path.join(user_dir, filename)):
        return jsonify({'error': 'file not found'}), 404
    return send_from_directory(user_dir, filename, as_attachment=True)


@app.route('/files/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    username, meta = current_user()
    user_dir = os.path.join(STORAGE_DIR, username)
    path = os.path.join(user_dir, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'file not found'}), 404
    os.remove(path)
    return jsonify({'status': 'deleted', 'filename': filename})


# ---- Admin endpoints ----
def require_admin(user_meta):
    if not getattr(user_meta, 'is_admin', False):
        abort(403, description='admin required')


@app.route('/admin/users', methods=['GET'])
def admin_list_users():
    _, meta = current_user()
    require_admin(meta)
    with app.app_context():
        users = User.query.order_by(User.username).all()
        results = []
        for u in users:
            results.append({
                'username': u.username,
                'is_admin': u.is_admin,
                'quota': u.quota,
                'usage': user_usage_bytes(u.username)
            })
    return jsonify({'users': results})


@app.route('/admin/users', methods=['POST'])
def admin_create_user():
    _, meta = current_user()
    require_admin(meta)
    data = request.json or {}
    username = data.get('username')
    quota = int(data.get('quota', 0))
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    with app.app_context():
        existing = User.query.get(username)
        if existing:
            return jsonify({'error': 'user exists'}), 400
        new_user = User(username=username, is_admin=False, quota=quota,
                        password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
    return jsonify({'status': 'created', 'username': username})


@app.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    with app.app_context():
        user = User.query.get(username)
        if not user:
            return jsonify({'error': 'invalid credentials'}), 401
        if not check_password_hash(user.password_hash, password):
            return jsonify({'error': 'invalid credentials'}), 401
        token = create_token(user.username, user.is_admin, expires_in=3600)
        return jsonify({'access_token': token, 'token_type': 'Bearer', 'expires_in': 3600})


@app.route('/admin/users/<username>/quota', methods=['PUT'])
def admin_update_quota(username):
    _, meta = current_user()
    require_admin(meta)
    data = request.json or {}
    quota = int(data.get('quota', 0))
    with app.app_context():
        user = User.query.get(username)
        if not user:
            return jsonify({'error': 'user not found'}), 404
        user.quota = quota
        db.session.commit()
    return jsonify({'status': 'updated', 'username': username, 'quota': quota})


if __name__ == '__main__':
    # For local testing only; in production front-end Apache should reverse proxy to this service.
    ensure_environment()
    app.run(host='0.0.0.0', port=5000)