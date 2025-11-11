import datetime
import os
from typing import Tuple, Optional

import jwt
from flask import request, abort
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User


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
            payload = jwt.decode(
                token,
                os.environ.get('SECRET_KEY', 'dev-secret-key'),
                algorithms=['HS256']
            )
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

    user = User.query.get(username)
    if not user:
        abort(403, description='Unknown user')

    return username, user


def create_token(username: str, is_admin: bool, expires_in: int = 3600) -> str:
    """Create JWT token for user authentication.

    Args:
        username: User's username
        is_admin: Whether user is admin
        expires_in: Token expiration time in seconds

    Returns:
        JWT token string
    """
    secret = os.environ.get('SECRET_KEY', 'dev-secret-key')
    exp = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)

    # Get user role from database
    user = User.query.get(username)
    role = getattr(user, 'role', 'user') if user else ('admin' if is_admin else 'user')

    payload = {
        'sub': username,
        'is_admin': bool(is_admin),
        'role': role,
        'exp': exp
    }
    return jwt.encode(payload, secret, algorithm='HS256')


def require_admin(user: User) -> None:
    """Check if user has admin privileges.

    Args:
        user: User object

    Raises:
        403: User is not admin
    """
    if not getattr(user, 'is_admin', False):
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