import datetime
import logging
from typing import Tuple, Optional

import jwt
from flask import request, abort, current_app

from .models import db, LdapUser

logger = logging.getLogger(__name__)


def get_ldap_client():
    """Get LDAP client from app config.
    
    Returns:
        LDAP client instance
        
    Raises:
        RuntimeError: If LDAP client is not available
    """
    try:
        ldap_client = current_app.config.get('LDAP_CLIENT')
        if not ldap_client:
            raise RuntimeError("LDAP client not initialized")
        return ldap_client
    except Exception as e:
        logger.error(f"Could not access LDAP client: {e}")
        raise RuntimeError("LDAP client not available") from e


def get_jwt_secret() -> str:
    """Get JWT secret from app config (which fetches from Vault).
    
    Returns:
        JWT signing secret
        
    Raises:
        RuntimeError: If secret key is not available
    """
    try:
        secret = current_app.config['SECRET_KEY']
        if not secret:
            raise RuntimeError("SECRET_KEY is empty")
        return secret
    except (RuntimeError, KeyError) as e:
        logger.error(f"Could not access SECRET_KEY: {e}")
        raise RuntimeError("JWT secret not available from Vault. Ensure Vault is configured and accessible.") from e


def authenticate_user() -> Tuple[str, LdapUser, str]:
    """Authenticate request using Bearer JWT in Authorization header.

    Returns:
        Tuple of (username, ldap_user_object, role)

    Raises:
        401: Missing or invalid authentication
        403: Unknown user
    """
    auth = request.headers.get('Authorization')
    if not auth or not auth.startswith('Bearer '):
        logger.warning("Missing or invalid Authorization header")
        abort(401, description='Missing authentication token')
    
    token = auth.split(' ', 1)[1].strip()
    
    try:
        secret = get_jwt_secret()
        payload = jwt.decode(
            token,
            secret,
            algorithms=['HS256']
        )
        username = payload.get('sub')
        role = payload.get('role', 'user')
    except jwt.ExpiredSignatureError:
        logger.warning("Attempt to use expired JWT token")
        abort(401, description='token expired')
    except Exception as e:
        logger.warning(f"Invalid JWT token: {e}")
        abort(401, description='invalid token')

    if not username:
        abort(401, description='Invalid token: missing username')

    # Get LDAP user from database
    user = LdapUser.query.get(username)
    if not user:
        logger.warning(f"Authentication attempted for unknown user: {username}")
        abort(403, description='Unknown user')

    return username, user, role


def create_token(username: str, role: str, expires_in: int = 3600) -> str:
    """Create JWT token for user authentication.

    Args:
        username: User's username
        role: User's role from LDAP
        expires_in: Token expiration time in seconds

    Returns:
        JWT token string
    """
    secret = get_jwt_secret()
    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)

    payload = {
        'sub': username,
        'role': role,
        'exp': exp
    }
    
    token = jwt.encode(payload, secret, algorithm='HS256')
    logger.info(f"Created JWT token for user: {username} with role: {role}")
    return token


def authenticate_ldap(username: str, password: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Authenticate user against LDAP and determine their role.

    Args:
        username: Username to authenticate
        password: Password to verify

    Returns:
        Tuple of (success: bool, role: Optional[str], error: Optional[str])
    """
    try:
        ldap_client = get_ldap_client()
        
        # Authenticate against LDAP
        success, error = ldap_client.authenticate(username, password)
        
        if not success:
            return False, None, error
        
        # Get user's role from LDAP groups
        role = ldap_client.get_user_role(username)
        
        # Create or update user in database (only quota and last_login)
        user = LdapUser.query.get(username)
        if not user:
            user = LdapUser(username=username)
            db.session.add(user)
            logger.info(f"Created new LDAP user in database: {username}")
        
        # Update last login timestamp
        user.last_login = datetime.datetime.utcnow()
        
        db.session.commit()
        
        return True, role, None
        
    except Exception as e:
        logger.error(f"LDAP authentication error for user {username}: {e}")
        return False, None, "Authentication service unavailable"


def require_admin(role: str) -> None:
    """Check if user has admin privileges.

    Args:
        role: User's role

    Raises:
        403: User is not admin
    """
    if role != 'admin':
        abort(403, description='admin required')