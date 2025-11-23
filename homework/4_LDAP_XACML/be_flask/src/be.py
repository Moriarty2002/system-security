#!/usr/bin/env python3
"""
Flask backend application for file storage service.

This application provides a REST API for user authentication,
file upload/download/management, and administrative functions.

Security Features:
- HashiCorp Vault integration for secrets management
- JWT-based authentication with Vault-managed signing keys
- Database credentials managed by Vault
- Secure password hashing for user accounts
"""

import os
import re
import logging
from flask import Flask
from flask_cors import CORS

from .config import get_config
from .models import db
from .utils import ensure_storage_directory
from .blueprints.auth import auth_bp
from .blueprints.files import files_bp
from .blueprints.admin import admin_bp


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
    else:
        # In development, also log to console
        app.logger.setLevel(logging.DEBUG)


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
    
    # Log Vault status and database URI
    if hasattr(config, 'vault_client'):
        if config.vault_client.is_available():
            app.logger.info("✅ Vault integration enabled - secrets managed by Vault")
        else:
            app.logger.warning("⚠️  Vault unavailable - using fallback configuration")
    
    # Log database connection (without exposing password)
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri:
        # Mask password in log
        import re
        masked_uri = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', db_uri)
        app.logger.info(f"Database URI: {masked_uri}")

    # Initialize extensions
    CORS(app)
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Initialize storage and database
    with app.app_context():
        ensure_storage_directory(app.config['STORAGE_DIR'])
        
        try:
            # Create table metadata (does NOT create tables if they exist)
            # This ensures SQLAlchemy knows about existing tables created by init script
            # In production: tables are created by DB migrations/init scripts, not Flask
            db.create_all()
            app.logger.info("Database schema synchronized")
        except Exception as e:
            app.logger.error(f"Failed to synchronize database schema: {e}")
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'not set')
            masked_uri = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', db_uri)
            app.logger.error(f"Database URI (masked): {masked_uri}")
            raise
        
        app.logger.info("Application initialized successfully")

    return app


app = create_app()

if __name__ == '__main__':
    # For local testing only; in production front-end Apache should reverse proxy to this service.
    app.run(host='0.0.0.0', port=5000)