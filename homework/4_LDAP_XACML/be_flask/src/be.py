#!/usr/bin/env python3
"""
Flask backend application for file storage service.

This application provides a REST API for user authentication,
file upload/download/management, and administrative functions.
"""

import os
import logging
from flask import Flask
from flask_cors import CORS

from .config import get_config
from .models import db
from .utils import ensure_storage_directory
from .blueprints.auth import auth_bp
from .blueprints.files import files_bp
from .blueprints.admin import admin_bp
from .models import User
from .auth import hash_password


def setup_logging(app: Flask) -> None:
    """Setup logging configuration."""
    if not app.debug:
        # In production, log to file
        log_file = os.path.join(os.path.dirname(__file__), 'app.log')
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)


def create_app(config_object=None) -> Flask:
    """Application factory function.

    Args:
        config_object: Configuration class to use

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Load configuration
    if config_object:
        app.config.from_object(config_object)
        config = config_object
    else:
        config = get_config()
        app.config.from_object(config)

    # Add storage directory to config
    app.config['STORAGE_DIR'] = config.STORAGE_DIR

    # Setup logging
    setup_logging(app)

    # Initialize extensions
    CORS(app)
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Initialize storage
    with app.app_context():
        ensure_storage_directory(app.config['STORAGE_DIR'])
        db.create_all()  # Create database tables
        # Ensure default users exist or update their passwords from env vars.
        # This makes the container-friendly `ADMIN_PASSWORD`, `ALICE_PASSWORD`,
        # and `MOD_PASSWORD` environment variables deterministic for local testing.
        try:
            defaults = [
                ("admin", "admin", 0, os.environ.get('ADMIN_PASSWORD')),
                ("alice", "user", 104857600, os.environ.get('ALICE_PASSWORD')),
                ("moderator", "moderator", 0, os.environ.get('MOD_PASSWORD')),
            ]
            for username, role, quota, pw in defaults:
                if pw is None:
                    # If no env pw provided, skip overriding existing entries.
                    continue
                user = User.query.get(username)
                if user:
                    user.password_hash = hash_password(pw)
                    user.role = role
                    user.quota = quota
                else:
                    user = User(username=username, role=role, quota=quota, password_hash=hash_password(pw))
                    db.session.add(user)
            db.session.commit()
        except Exception:
            app.logger.exception('failed to ensure default users')
        app.logger.info("Application initialized successfully")

    return app


app = create_app()

if __name__ == '__main__':
    # For local testing only; in production front-end Apache should reverse proxy to this service.
    app.run(host='0.0.0.0', port=5000)