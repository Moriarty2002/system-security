import logging
from flask import Blueprint, jsonify, request

from ..auth import authenticate_user, create_token, verify_password, hash_password
from ..models import db, User

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/whoami', methods=['GET'])
def whoami():
    """Return current authenticated user's basic metadata (username, role).

    This endpoint helps the front-end adapt UI to the user's role.
    """
    try:
        username, user = authenticate_user()
        logger.info(f"User {username} requested their profile information")
        return jsonify({
            'username': username,
            'role': getattr(user, 'role', 'user')
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

        user = User.query.get(username)
        if not user:
            logger.warning(f"Login attempt for non-existent user: {username}")
            return jsonify({'error': 'invalid credentials'}), 401

        if not verify_password(user.password_hash, password):
            logger.warning(f"Failed login attempt for user: {username}")
            return jsonify({'error': 'invalid credentials'}), 401

        token = create_token(user.username, expires_in=3600)
        logger.info(f"Successful login for user: {username}")
        return jsonify({
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': 3600
        })
    except Exception as e:
        logger.error(f"Error in login endpoint: {str(e)}")
        return jsonify({'error': 'internal server error'}), 500