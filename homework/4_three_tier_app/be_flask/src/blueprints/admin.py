from flask import Blueprint, jsonify, request, current_app

from ..keycloak_auth import authenticate_user, require_admin, get_admin_keycloak_auth, require_admin_moderator
from ..models import db, UserProfile
from ..utils_s3 import get_user_usage_bytes

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
def list_users():
    """List all users with their details (admin and moderators only)."""
    authenticate_user()
    require_admin_moderator()

    users = UserProfile.query.all()
    results = []
    
    # Get Keycloak admin API client
    kc = None
    kc = get_admin_keycloak_auth()

    s3_client = current_app.config.get('S3_CLIENT')

    # Fetch user details from Keycloak
    keycloak_ids = [str(u.keycloak_id) for u in users]
    users_data = kc.admin_get_users_with_roles(keycloak_ids)
    
    for u in users:
        keycloak_id_str = str(u.keycloak_id)
        user_info = users_data.get(keycloak_id_str)
        
        if not user_info:
            continue
        
        # Filter: only include users with 'user' realm role
        if 'user' not in user_info.get('roles', []):
            continue
        
        username = user_info.get('username', 'Unknown')
        
        # Calculate used quota
        used_quota = 0
        if s3_client and username != 'Unknown':
            try:
                used_quota = get_user_usage_bytes(username, s3_client)
            except Exception:
                used_quota = 0

        results.append({
            'keycloak_id': keycloak_id_str,
            'role': 'Managed by Keycloak',
            'quota': u.quota,
            'used_quota': used_quota,
            'username': username
        })

    return jsonify({'users': results})


@admin_bp.route('/users/<keycloak_id>/quota', methods=['PUT'])
def update_quota(keycloak_id):
    """Update user quota (admin only). Use keycloak_id, not username."""
    authenticate_user()
    require_admin()

    target_user = UserProfile.query.filter_by(keycloak_id=keycloak_id).first()
    if not target_user:
        return jsonify({'error': 'user not found'}), 404

    data = request.json or {}
    try:
        quota = int(data.get('quota', 0))
        if quota < 0:
            return jsonify({'error': 'quota must be non-negative'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'quota must be a valid integer'}), 400

    target_user.quota = quota
    db.session.commit()

    return jsonify({'status': 'updated', 'keycloak_id': keycloak_id, 'quota': quota})


@admin_bp.route('/users/<keycloak_id>', methods=['DELETE'])
def delete_user(keycloak_id):
    """Delete a user profile (admin only). Use keycloak_id, not username.
    
    Note: This only deletes the application profile.
    To fully remove a user, they must also be deleted from Keycloak.
    """
    from flask import g
    
    authenticate_user()
    require_admin()

    # Prevent admin from deleting themselves
    if keycloak_id == str(g.user_profile.keycloak_id):
        return jsonify({'error': 'cannot delete yourself'}), 403

    target_user = UserProfile.query.filter_by(keycloak_id=keycloak_id).first()
    if not target_user:
        return jsonify({'error': 'user not found'}), 404

    # Delete the user profile
    db.session.delete(target_user)
    db.session.commit()

    return jsonify({
        'status': 'deleted',
        'keycloak_id': keycloak_id,
        'note': 'User profile deleted. User still exists in Keycloak and must be deleted there separately.'
    })