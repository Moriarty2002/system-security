import logging
from flask import Blueprint, jsonify, current_app, g
import requests

from ..keycloak_auth import authenticate_user, get_keycloak_auth

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/whoami', methods=['GET'])
def whoami():
    """Return current authenticated user's basic metadata (username, role).

    This endpoint helps the front-end adapt UI to the user's role.
    All authentication is handled by Keycloak.
    Role is fetched fresh from Keycloak token (not from database).
    """
    try:
        username, user_profile = authenticate_user()
        logger.info(f"User {username} requested their profile information")
        return jsonify({
            'username': username,
            'role': g.user_role,  # Fresh from Keycloak token
            'keycloak_id': str(user_profile.keycloak_id)
        })
    except Exception as e:
        logger.error(f"Error in whoami endpoint: {str(e)}")
        raise


@auth_bp.route('/config', methods=['GET'])
def auth_config():
    """Return Keycloak configuration for frontend authentication.
    
    This endpoint provides the frontend with necessary Keycloak configuration
    to initiate the authentication flow.
    Uses external URL (localhost) for browser access.
    """
    try:
        return jsonify({
            'server_url': current_app.config.get('KEYCLOAK_SERVER_URL_EXTERNAL'),
            'realm': current_app.config.get('KEYCLOAK_REALM'),
            'client_id': current_app.config.get('KEYCLOAK_CLIENT_ID')
        })
    except Exception as e:
        logger.error(f"Error in auth_config endpoint: {str(e)}")
        return jsonify({'error': 'Configuration unavailable'}), 500
