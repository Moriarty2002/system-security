import os
from typing import Optional


class Config:
    """Base configuration class."""

    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Database URI configuration with fallback to SQLite."""
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            return database_url

        # SQLite file next to this script for local testing
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sqlite_path = os.path.join(base_dir, 'homework.db')
        return f"sqlite:///{sqlite_path}"

    @property
    def STORAGE_DIR(self) -> str:
        """Storage directory for user files."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, 'storage')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


def get_config() -> Config:
    """Get configuration based on environment."""
    env = os.environ.get('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig()
    return DevelopmentConfig()