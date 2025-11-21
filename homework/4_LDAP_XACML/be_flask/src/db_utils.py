"""
Database initialization utilities.

This module provides functions to initialize the database with default users
using passwords from Vault or environment variables.
"""

import logging
from werkzeug.security import generate_password_hash

from .models import db, User
from .config import Config

logger = logging.getLogger(__name__)


def initialize_default_users(config: Config) -> None:
    """Initialize default users (admin, alice, moderator) if they don't exist.
    
    This function reads default passwords from Vault and creates users if needed.
    Should be called during application initialization.
    
    Args:
        config: Application configuration object with Vault access
    """
    default_users = [
        {
            'username': 'admin',
            'role': 'admin',
            'quota': 0,
            'password_key': 'admin_password'
        },
        {
            'username': 'alice',
            'role': 'user',
            'quota': 104857600,  # 100 MB
            'password_key': 'alice_password'
        },
        {
            'username': 'moderator',
            'role': 'moderator',
            'quota': 0,
            'password_key': 'moderator_password'
        }
    ]
    
    users_created = 0
    
    for user_data in default_users:
        username = user_data['username']
        
        # Check if user already exists
        existing_user = User.query.get(username)
        if existing_user:
            logger.debug(f"User '{username}' already exists, skipping")
            continue
        
        # Get password from config (which gets it from Vault)
        password = config.get_user_password(username)
        password_hash = generate_password_hash(password)
        
        # Create new user
        new_user = User(
            username=username,
            role=user_data['role'],
            quota=user_data['quota'],
            password_hash=password_hash
        )
        
        db.session.add(new_user)
        users_created += 1
        logger.info(f"Created default user: {username} with role {user_data['role']}")
    
    if users_created > 0:
        try:
            db.session.commit()
            logger.info(f"Successfully initialized {users_created} default user(s)")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to commit default users: {e}")
            raise
    else:
        logger.info("All default users already exist")


def check_database_health() -> bool:
    """Check if database connection is healthy.
    
    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        # Try a simple query
        db.session.execute(db.text('SELECT 1'))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
