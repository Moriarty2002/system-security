from flask import Blueprint, jsonify, request, current_app

from ..auth import authenticate_user, require_admin, hash_password
from ..models import db, User
from ..utils import get_user_usage_bytes

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
def list_users():
    """List all users with their details (admin only)."""
    _, user = authenticate_user()
    require_admin(user)

    users = User.query.order_by(User.username).all()
    results = []
    for u in users:
        results.append({
            'username': u.username,
            'role': u.role,
            'quota': u.quota,
            'usage': get_user_usage_bytes(u.username, current_app.config['STORAGE_DIR'])
        })

    return jsonify({'users': results})


@admin_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user (admin only)."""
    _, user = authenticate_user()
    require_admin(user)

    data = request.json or {}
    username = data.get('username')
    quota = int(data.get('quota', 0))
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    existing = User.query.get(username)
    if existing:
        return jsonify({'error': 'user exists'}), 400

    new_user = User()
    new_user.username = username
    new_user.quota = quota
    new_user.password_hash = hash_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'status': 'created', 'username': username})


@admin_bp.route('/users/<username>/quota', methods=['PUT'])
def update_quota(username):
    """Update user quota (admin only)."""
    _, user = authenticate_user()
    require_admin(user)

    data = request.json or {}
    quota = int(data.get('quota', 0))

    target_user = User.query.get(username)
    if not target_user:
        return jsonify({'error': 'user not found'}), 404

    target_user.quota = quota
    db.session.commit()

    return jsonify({'status': 'updated', 'username': username, 'quota': quota})