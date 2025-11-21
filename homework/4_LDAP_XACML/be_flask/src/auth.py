import datetime
import logging
from typing import Tuple

import jwt
from flask import request, abort, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from .models import db, User

logger = logging.getLogger(__name__)


def get_jwt_secret() -> str:
    """Get JWT secret from app config (which fetches from Vault).
    
    Returns:
        JWT signing secret
    """
    try:
        return current_app.config['SECRET_KEY']
    except (RuntimeError, KeyError):
        # Fallback if not in app context
        logger.warning("Could not access Flask app context for SECRET_KEY")
        import os
        return os.environ.get('SECRET_KEY', 'dev-secret-key')


def authenticate_user() -> Tuple[str, User]:
    """Authenticate request using Bearer JWT in Authorization header.

    Falls back to X-User header only for quick local testing (not recommended).

    Returns:
        Tuple of (username, user_object)

    Raises:
        401: Missing or invalid authentication
        403: Unknown user
    """
    auth = request.headers.get('Authorization')
    token = None
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1].strip()

    username = None
    if token:
        try:
            secret = get_jwt_secret()
            payload = jwt.decode(
                token,
                secret,
                algorithms=['HS256']
            )
            username = payload.get('sub')
        except jwt.ExpiredSignatureError:
            logger.warning("Attempt to use expired JWT token")
            abort(401, description='token expired')
        except Exception as e:
            logger.warning(f"Invalid JWT token: {e}")
            abort(401, description='invalid token')
    else:
        # fallback - NOT secure, only for local/demo convenience
        username = request.headers.get('X-User')

    if not username:
        abort(401, description='Missing authentication')

    user = User.query.get(username)
    if not user:
        logger.warning(f"Authentication attempted for unknown user: {username}")
        abort(403, description='Unknown user')

    return username, user


def create_token(username: str, expires_in: int = 3600) -> str:
    """Create JWT token for user authentication.

    Args:
        username: User's username
        expires_in: Token expiration time in seconds

    Returns:
        JWT token string
    """
    secret = get_jwt_secret()
    exp = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)

    # Get user role from database
    user = User.query.get(username)
    role = getattr(user, 'role', 'user') if user else 'user'

    payload = {
        'sub': username,
        'role': role,
        'exp': exp
    }
    
    token = jwt.encode(payload, secret, algorithm='HS256')
    logger.info(f"Created JWT token for user: {username}")
    return token


def require_admin(user: User) -> None:
    """Check if user has admin privileges.

    Args:
        user: User object

    Raises:
        403: User is not admin
    """
    if getattr(user, 'role', 'user') != 'admin':
        abort(403, description='admin required')


def hash_password(password: str) -> str:
    """Hash a password for storage.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against its hash.

    Args:
        password_hash: Hashed password
        password: Plain text password

    Returns:
        True if password matches hash
    """
    return check_password_hash(password_hash, password)