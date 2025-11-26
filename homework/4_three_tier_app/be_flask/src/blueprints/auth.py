import logging
from flask import Blueprint, jsonify, request

from ..auth import authenticate_user, create_token, authenticate_ldap
from ..models import db, LdapUser

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/whoami', methods=['GET'])
def whoami():
    """Return current authenticated user's basic metadata (username, role).

    This endpoint helps the front-end adapt UI to the user's role.
    """
    try:
        username, user, role = authenticate_user()
        logger.info(f"User {username} requested their profile information")
        return jsonify({
            'username': username,
            'role': role
        })
    except Exception as e:
        logger.error(f"Error in whoami endpoint: {str(e)}")
        raise


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token."""
    try:
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            logger.warning("Login attempt with missing credentials")
            return jsonify({'error': 'username and password required'}), 400

        # Authenticate against LDAP
        success, role, error = authenticate_ldap(username, password)
        
        if not success:
            logger.warning(f"Failed login attempt for user: {username}")
            return jsonify({'error': error or 'invalid credentials'}), 401

        # Create JWT token with role from LDAP
        token = create_token(username, role, expires_in=3600)
        logger.info(f"Successful login for user: {username} with role: {role}")
        return jsonify({
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': 3600
        })
    except Exception as e:
        logger.error(f"Error in login endpoint: {str(e)}")
        return jsonify({'error': 'internal server error'}), 500