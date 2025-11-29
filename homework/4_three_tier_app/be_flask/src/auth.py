"""
DEPRECATED: Legacy authentication module.

This module is deprecated and kept only for reference.
All authentication has been migrated to Keycloak.

Use keycloak_auth.py for all authentication operations.
"""

import logging
from flask import abort
from werkzeug.security import generate_password_hash, check_password_hash

from .models import User

logger = logging.getLogger(__name__)


# DEPRECATED - Kept for backward compatibility only
def hash_password(password: str) -> str:
    """Hash a password for storage.
    
    DEPRECATED: Passwords are now managed by Keycloak.
    This function is kept only for migration scripts.
    
    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    logger.warning("DEPRECATED: hash_password called. Use Keycloak for password management.")
    return generate_password_hash(password)


# DEPRECATED - Kept for backward compatibility only
def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against its hash.
    
    DEPRECATED: Passwords are now managed by Keycloak.
    This function is kept only for legacy data migration.
    
    Args:
        password_hash: Hashed password
        password: Plain text password

    Returns:
        True if password matches hash
    """
    logger.warning("DEPRECATED: verify_password called. Use Keycloak for authentication.")
    return check_password_hash(password_hash, password)