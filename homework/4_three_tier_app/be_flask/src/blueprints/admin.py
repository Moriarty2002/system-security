from flask import Blueprint, jsonify, request

from ..keycloak_auth import authenticate_user, require_admin, get_admin_keycloak_auth
from ..models import db, UserProfile

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
def list_users():
    """List all users with their details (admin only)."""
    authenticate_user()
    require_admin()

    users = UserProfile.query.all()
    results = []
    # Attempt to resolve human-friendly usernames from Keycloak Admin API if available.
    kc = None
    try:
        kc = get_admin_keycloak_auth()
    except Exception:
        kc = None

    for u in users:
        username = 'See Keycloak'
        try:
            if kc:
                kc_user = kc.admin_get_user(str(u.keycloak_id))
                if kc_user and kc_user.get('username'):
                    username = kc_user.get('username')
        except Exception:
            # Any failure to call Keycloak admin API should not prevent listing users
            username = 'See Keycloak'

        results.append({
            'keycloak_id': str(u.keycloak_id),
            'role': 'Managed by Keycloak',  # Role not stored in DB
            'quota': u.quota,
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