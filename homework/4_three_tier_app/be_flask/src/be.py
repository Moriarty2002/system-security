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
import logging
from flask import Flask
from flask_cors import CORS
import re
from flask import request, jsonify
from datetime import datetime
from .config import get_config
from .models import db
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

    # If Vault is available, attempt to install CA chain from Vault into system trust
    try:
        # Ensure config.vault_client is created lazily
        if hasattr(config, 'vault_client') and config.vault_client.is_available():
            app.logger.info('Attempting to fetch CA chain from Vault to populate trust store')
            app_secrets = config.vault_client.get_app_secrets() or {}
            ca_chain = app_secrets.get('CA_chain') or app_secrets.get('ca_chain')
            if ca_chain:
                ca_path = '/usr/local/share/ca-certificates/vault_pki_ca.crt'
                # Only write/install if not already present or different
                existing = None
                if os.path.exists(ca_path):
                    with open(ca_path, 'r') as f:
                        existing = f.read()
                if existing != ca_chain:
                    with open(ca_path, 'w') as f:
                        f.write(ca_chain)
                    # update system CA store if available
                    import shutil, subprocess
                    if shutil.which('update-ca-certificates'):
                        subprocess.run(['update-ca-certificates'], check=False)
                        app.logger.info('Installed Vault PKI CA into system trust store')
                        # Ensure Python requests uses the system CA bundle (not certifi's bundle)
                        system_bundle = '/etc/ssl/certs/ca-certificates.crt'
                        os.environ.setdefault('REQUESTS_CA_BUNDLE', system_bundle)
                        os.environ.setdefault('SSL_CERT_FILE', system_bundle)
                        app.logger.info(f'Set REQUESTS_CA_BUNDLE and SSL_CERT_FILE to {system_bundle}')
                    else:
                        app.logger.warning('update-ca-certificates not found; CA written but not installed')
                else:
                    app.logger.info('Vault PKI CA already present in trust store')
            else:
                app.logger.debug('No CA_chain found in Vault app secrets; skipping CA install')
    except Exception as e:
        app.logger.error(f'Failed to loading configurations from Vault: {e}')
        raise

    # Initialize S3 client
    try:
        app.config['S3_CLIENT'] = config.get_s3_client()
    except Exception as e:
        print(f"❌ Failed to initialize S3 client: {e}")
        raise

    # Setup logging
    setup_logging(app)
    
    # Log S3 initialization status
    app.logger.info("✅ S3 client initialized - using AWS S3 with Roles Anywhere authentication")
    
    # Log Vault status and database URI
    if hasattr(config, 'vault_client'):
        if config.vault_client.is_available():
            app.logger.info("✅ Vault integration enabled - secrets managed by Vault")
        else:
            raise RuntimeError("Vault is not available. Application requires Vault for all configuration.")
    
    # Log database connection (without exposing password)
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        raise RuntimeError("SQLALCHEMY_DATABASE_URI not configured")
    # Mask password in log
    masked_uri = re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', db_uri)
    app.logger.info(f"Database URI: {masked_uri}")

    # Initialize extensions
    CORS(app, resources={
    r"/api/*": {
        "origins": ["https://localhost"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Authorization", "Content-Type"],
        "expose_headers": ["Content-Range", "X-Content-Range"],
        "supports_credentials": True,
        "max_age": 3600
    }
})
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # AC-8 System Use Notification endpoint
    @app.route('/api/banner/acknowledge', methods=['POST'])
    def acknowledge_banner():
        """Log user acknowledgment of system use banner (AC-8 compliance)."""
        
        data = request.get_json() or {}
        timestamp = data.get('timestamp', datetime.utcnow().isoformat())
        user_agent = data.get('userAgent', request.headers.get('User-Agent', 'unknown'))
        ip_address = request.remote_addr
        
        # Log the acknowledgment
        app.logger.info(
            f"[AC-8][BANNER_ACKNOWLEDGED] IP: {ip_address}, "
            f"User-Agent: {user_agent}, Timestamp: {timestamp}"
        )
        
        return jsonify({
            'status': 'acknowledged',
            'timestamp': timestamp,
            'logged': True
        })

    # Initialize database
    with app.app_context():
        
        try:
            # Create table metadata (does NOT create tables if they exist)
            # This ensures SQLAlchemy knows about existing tables created by init script
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