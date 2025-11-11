import os
import datetime
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger, inspect, text
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
    # role: 'user', 'admin', 'moderator' - kept as separate column to be explicit
    role = db.Column(db.String(32), nullable=False, default='user')
    quota = db.Column(BigInteger, nullable=False, default=0)
    password_hash = db.Column(db.String(256), nullable=False)


def ensure_environment():
    os.makedirs(STORAGE_DIR, exist_ok=True)
    # Database schema and seed data are created by the Postgres init SQL
    # scripts (./be_flask/db_init) mounted into the postgres container.
    # We intentionally do not create or mutate the DB schema here so the
    # database is authoritative for its schema and initial data.
    # Create local storage directories only.


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
    # include role in token when available
    with app.app_context():
        u = User.query.get(username)
        role = getattr(u, 'role', 'user') if u else ('admin' if is_admin else 'user')
    payload = {'sub': username, 'is_admin': bool(is_admin), 'role': role, 'exp': exp}
    return jwt.encode(payload, secret, algorithm='HS256')


@app.route('/auth/whoami', methods=['GET'])
def auth_whoami():
    """Return current authenticated user's basic metadata (username, role, is_admin).

    This endpoint helps the front-end adapt UI to the user's role.
    """
    username, meta = current_user()
    return jsonify({'username': username, 'role': getattr(meta, 'role', 'user'), 'is_admin': meta.is_admin})


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
    # werkzeug's FileStorage.filename can be None in some cases; normalize to str
    filename_raw = f.filename or ''
    if filename_raw == '':
        return jsonify({'error': 'no selected file'}), 400

    filename = secure_filename(filename_raw)
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

        # Save file to destination. Use a streaming write to ensure the uploaded
        # content is written to the final path (some servers may use temp files).
        save_path = os.path.join(user_dir, filename)
        try:
            # ensure stream pointer at start
            try:
                file_stream.seek(0)
            except Exception:
                pass
            with open(save_path, 'wb') as out_f:
                while True:
                    chunk = file_stream.read(8192)
                    if not chunk:
                        break
                    out_f.write(chunk)
                out_f.flush()
                try:
                    os.fsync(out_f.fileno())
                except Exception:
                    # fsync may not be available on all platforms/FS; ignore if it fails
                    pass
        except Exception as e:
            # If saving fails, return an error so front-end can react
            return jsonify({'error': 'failed to save file', 'detail': str(e)}), 500
        # No DB metadata to update for file uploads; commit to release locks
        db.session.commit()

    return jsonify({'status': 'ok', 'filename': filename, 'size': file_size})


@app.route('/files', methods=['GET'])
def list_files():
    username, meta = current_user()
    # allow moderators/admins to view other users' file lists via ?user=<username>
    target = request.args.get('user') or username
    if target != username and getattr(meta, 'role', '') not in ('admin', 'moderator'):
        abort(403, description='insufficient role to view other users')

    files = user_files_list(target)
    usage = user_usage_bytes(target)
    quota = None
    if target == username:
        quota = meta.quota
    else:
        with app.app_context():
            u = User.query.get(target)
            quota = u.quota if u else 0
    return jsonify({'files': files, 'usage': usage, 'quota': quota, 'user': target})


@app.route('/files/<path:filename>', methods=['GET'])
def download_file(filename):
    username, meta = current_user()
    # allow moderators/admins to download other users' files via ?user=<username>
    target = request.args.get('user') or username
    if target != username and getattr(meta, 'role', '') not in ('admin', 'moderator'):
        abort(403, description='insufficient role to download other users files')
    user_dir = os.path.join(STORAGE_DIR, target)
    # prevent path traversal by using send_from_directory
    if not os.path.exists(os.path.join(user_dir, filename)):
        return jsonify({'error': 'file not found'}), 404
    return send_from_directory(user_dir, filename, as_attachment=True)


@app.route('/files/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    username, meta = current_user()
    # Deletions only allowed by owner or admin (moderator cannot delete)
    target = request.args.get('user') or username
    if target != username and not getattr(meta, 'is_admin', False):
        abort(403, description='only owner or admin can delete files')
    user_dir = os.path.join(STORAGE_DIR, target)
    path = os.path.join(user_dir, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'file not found'}), 404
    os.remove(path)
    return jsonify({'status': 'deleted', 'filename': filename, 'user': target})


@app.route('/users', methods=['GET'])
def list_usernames():
    """Return a simple list of usernames. Allowed for admin and moderator roles."""
    username, meta = current_user()
    if getattr(meta, 'role', '') not in ('admin', 'moderator'):
        abort(403, description='insufficient role to list users')
    with app.app_context():
        users = User.query.order_by(User.username).all()
        return jsonify({'users': [u.username for u in users]})


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