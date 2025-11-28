from flask import Blueprint, jsonify, request, current_app

from ..auth import authenticate_user
from ..models import db, LdapUser
from ..utils_minio import get_user_usage_bytes
from ..xacml_pep import enforce_xacml, require_xacml_permission

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
@enforce_xacml('admin-list-users')
def list_users():
    """List all users with their details (admin only)."""
    _, user, role = authenticate_user()
    
    minio_client = current_app.config['MINIO_CLIENT']
    ldap_client = current_app.config['LDAP_CLIENT']

    users = LdapUser.query.order_by(LdapUser.username).all()
    results = []
    for u in users:
        # Get role from LDAP for each user
        user_role = ldap_client.get_user_role(u.username)
        results.append({
            'username': u.username,
            'role': user_role,
            'quota': u.quota,
            'usage': get_user_usage_bytes(u.username, minio_client)
        })

    return jsonify({'users': results})


@admin_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user - DISABLED (users managed in LDAP)."""
    return jsonify({'error': 'User creation must be done through LDAP directory. Contact administrator.'}), 501


@admin_bp.route('/users/<username>/quota', methods=['PUT'])
def update_quota(username):
    """Update user quota (admin only)."""
    current_username, user, role = authenticate_user()

    target_user = LdapUser.query.get(username)
    if not target_user:
        return jsonify({'error': 'user not found'}), 404

    # Get target user's role from LDAP
    ldap_client = current_app.config['LDAP_CLIENT']
    target_role = ldap_client.get_user_role(username)
    
    # Check XACML authorization with target user's role
    require_xacml_permission(
        username=current_username,
        role=role,
        action='update-quota',
        target_role=target_role
    )

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
    """Delete a user - DISABLED (users managed in LDAP)."""
    return jsonify({'error': 'User deletion must be done through LDAP directory. Contact administrator.'}), 501