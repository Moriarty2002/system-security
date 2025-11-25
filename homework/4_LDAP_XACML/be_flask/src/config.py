import os
import logging

logger = logging.getLogger(__name__)


class Config:
    """Base configuration class with Vault integration."""

    def __init__(self):
        """Initialize configuration with Vault client."""
        self._vault_client = None
        self._app_secrets = None
        self._db_config = None

    @property
    def vault_client(self):
        """Lazy-load Vault client."""
        if self._vault_client is None:
            from .vault_client import get_vault_client
            self._vault_client = get_vault_client()
            if not self._vault_client.is_available():
                raise RuntimeError("Vault client is not available. Application requires Vault for configuration.")
        return self._vault_client

    @property
    def app_secrets(self):
        """Get application secrets from Vault with caching."""
        if self._app_secrets is None:
            self._app_secrets = self.vault_client.get_app_secrets()
        return self._app_secrets

    @property
    def SECRET_KEY(self) -> str:
        """JWT signing key from Vault (required)."""
        jwt_secret = self.app_secrets.get('jwt_secret')
        if not jwt_secret:
            raise RuntimeError("JWT secret not available from Vault")
        return jwt_secret

    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Database URI from Vault (required)."""
        if self._db_config is None:
            self._db_config = self.vault_client.get_database_config()
        
        if self._db_config and self._db_config.get('url'):
            logger.info("Using database configuration from Vault")
            return self._db_config['url']
        
        raise RuntimeError("Database configuration not available from Vault")

    @property
    def STORAGE_DIR(self) -> str:
        """Storage directory for user files."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, 'storage')

    def get_user_password(self, username: str) -> str:
        """Get default password for a user from Vault.
        
        Args:
            username: Username (admin, alice, moderator)
            
        Returns:
            Default password for the user
        """
        password_key = f'{username.lower()}_password'
        return self.app_secrets.get(password_key, username)


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