from flask import Blueprint, jsonify, request, current_app

from ..auth import authenticate_user, require_admin, hash_password
from ..models import db, User
from ..utils_minio import get_user_usage_bytes

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
def list_users():
    """List all users with their details (admin only)."""
    _, user = authenticate_user()
    require_admin(user)
    
    minio_client = current_app.config['MINIO_CLIENT']

    users = User.query.order_by(User.username).all()
    results = []
    for u in users:
        results.append({
            'username': u.username,
            'role': u.role,
            'quota': u.quota,
            'usage': get_user_usage_bytes(u.username, minio_client)
        })

    return jsonify({'users': results})


@admin_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user (admin only)."""
    _, user = authenticate_user()
    require_admin(user)

    data = request.json or {}
    username = data.get('username', '').strip()
    quota = data.get('quota', 0)
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400

    # Validate quota is non-negative integer
    try:
        quota = int(quota)
        if quota < 0:
            return jsonify({'error': 'quota must be non-negative'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'quota must be a valid integer'}), 400

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

    target_user = User.query.get(username)
    if not target_user:
        return jsonify({'error': 'user not found'}), 404

    # Prevent setting quotas for admin and moderator users
    if target_user.role in ('admin', 'moderator'):
        return jsonify({'error': f'cannot set quota for {target_user.role} users'}), 403

    data = request.json or {}
    try:
        quota = int(data.get('quota', 0))
        if quota < 0:
            return jsonify({'error': 'quota must be non-negative'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'quota must be a valid integer'}), 400

    target_user.quota = quota
    db.session.commit()

    return jsonify({'status': 'updated', 'username': username, 'quota': quota})


@admin_bp.route('/users/<username>', methods=['DELETE'])
def delete_user(username):
    """Delete a user (admin only)."""
    _, user = authenticate_user()
    require_admin(user)

    # Prevent admin from deleting themselves
    if username == user.username:
        return jsonify({'error': 'cannot delete yourself'}), 403

    target_user = User.query.get(username)
    if not target_user:
        return jsonify({'error': 'user not found'}), 404

    # Prevent deleting other admin users
    if target_user.role == 'admin':
        return jsonify({'error': 'cannot delete admin users'}), 403

    # Delete the user
    db.session.delete(target_user)
    db.session.commit()

    return jsonify({'status': 'deleted', 'username': username})