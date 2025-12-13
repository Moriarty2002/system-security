import os
import logging
from .vault_client import get_vault_client
from .s3_client import S3Client

logger = logging.getLogger(__name__)


class Config:
    """Base configuration class with Vault and Keycloak integration."""

    def __init__(self):
        """Initialize configuration with Vault client."""
        self._vault_client = None
        self._app_secrets = None
        self._db_config = None
        self._s3_client = None
        self._keycloak_config = None

    @property
    def vault_client(self):
        """Lazy-load Vault client."""
        if self._vault_client is None:
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
    def keycloak_config(self):
        """Get Keycloak configuration from Vault with caching."""
        if self._keycloak_config is None:
            # May return None if Vault does not contain the keycloak/client secret
            self._keycloak_config = self.vault_client.get_keycloak_config()
        return self._keycloak_config
    
    @property
    def KEYCLOAK_SERVER_URL_EXTERNAL(self) -> str:
        """Keycloak server URL for browser access (external)."""
        # Require Keycloak configuration to come from Vault. Do not read env vars.
        kc = self.keycloak_config
        if kc is None:
            raise RuntimeError('Vault secret `secret/keycloak/client` not found; KEYCLOAK_SERVER_URL_EXTERNAL unavailable')

        val = kc.get('server_url_external')
        if val is None:
            raise RuntimeError('KEYCLOAK_SERVER_URL_EXTERNAL missing in Vault secret `secret/keycloak/client`')
        return val

    @property
    def SECRET_KEY(self) -> str:
        """JWT signing key from Vault (kept for session management)."""
        jwt_secret = self.app_secrets.get('jwt_secret')
        if not jwt_secret:
            raise RuntimeError("JWT secret not available from Vault")
        return jwt_secret
    
    @property
    def KEYCLOAK_SERVER_URL(self) -> str:
        """Keycloak server URL from environment or Vault."""
        # Require Keycloak configuration to come from Vault. Do not read env vars.
        kc = self.keycloak_config
        if kc is None:
            raise RuntimeError('Vault secret `secret/keycloak/client` not found; KEYCLOAK_SERVER_URL unavailable')

        val = kc.get('server_url')
        if val is None:
            raise RuntimeError('KEYCLOAK_SERVER_URL missing in Vault secret `secret/keycloak/client`')
        return val
    
    @property
    def KEYCLOAK_REALM(self) -> str:
        """Keycloak realm name from environment or Vault."""
        # Require Keycloak configuration to come from Vault. Do not read env vars.
        kc = self.keycloak_config
        if kc is None:
            raise RuntimeError('Vault secret `secret/keycloak/client` not found; KEYCLOAK_REALM unavailable')

        val = kc.get('realm')
        if val is None:
            raise RuntimeError('KEYCLOAK_REALM missing in Vault secret `secret/keycloak/client`')
        return val
    
    @property
    def KEYCLOAK_CLIENT_ID(self) -> str:
        """Keycloak client ID from environment or Vault."""
        # Require Keycloak configuration to come from Vault. Do not read env vars.
        kc = self.keycloak_config
        if kc is None:
            raise RuntimeError('Vault secret `secret/keycloak/client` not found; KEYCLOAK_CLIENT_ID unavailable')

        val = kc.get('client_id')
        if val is None:
            raise RuntimeError('KEYCLOAK_CLIENT_ID missing in Vault secret `secret/keycloak/client`')
        return val
    
    @property
    def KEYCLOAK_CLIENT_SECRET(self) -> str:
        """Keycloak client secret from Vault (required for admin operations)."""
        # Require Keycloak configuration to come from Vault. Do not read env vars.
        kc = self.keycloak_config
        if kc is None:
            raise RuntimeError('Vault secret `secret/keycloak/client` not found; KEYCLOAK_CLIENT_SECRET unavailable')

        val = kc.get('client_secret')
        if val is None:
            raise RuntimeError('KEYCLOAK_CLIENT_SECRET missing in Vault secret `secret/keycloak/client`')
        return val

    @property
    def KEYCLOAK_CLIENT_ID_ADMIN(self) -> str:
        """Admin/service-account client id for backend admin calls.

        Falls back to `KEYCLOAK_CLIENT_ID` if not explicitly configured.
        """
        # Require Keycloak configuration to come from Vault. Do not read env vars.
        kc = self.keycloak_config
        if kc is None:
            raise RuntimeError('Vault secret `secret/keycloak/client` not found; KEYCLOAK_CLIENT_ID_ADMIN unavailable')

        val = kc.get('client_id_admin')
        if val is None:
            raise RuntimeError('KEYCLOAK_CLIENT_ID_ADMIN missing in Vault secret `secret/keycloak/client`')
        return val

    @property
    def KEYCLOAK_CLIENT_SECRET_ADMIN(self) -> str:
        """Admin/service-account client secret stored in Vault or env.

        Falls back to the general client secret if an admin secret isn't provided.
        """
        # Require Keycloak configuration to come from Vault. Do not read env vars.
        kc = self.keycloak_config
        if kc is None:
            raise RuntimeError('Vault secret `secret/keycloak/client` not found; KEYCLOAK_CLIENT_SECRET_ADMIN unavailable')

        val = kc.get('client_secret_admin')
        if val is None:
            raise RuntimeError('KEYCLOAK_CLIENT_SECRET_ADMIN missing in Vault secret `secret/keycloak/client`')
        return val

    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    
    # SC-10: Network Disconnect - Database connection pool settings
    # Terminate idle database connections to comply with NIST 800-53 SC-10
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        'pool_pre_ping': True,                   # Test connections before checkout
        'pool_recycle': 3600,                    # Recycle after 1 hour
        'pool_size': 10,                         # Base pool size
        'max_overflow': 5,                       # Max connections beyond pool_size
        'pool_timeout': 30,                      # Timeout waiting for connection
    }

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Database URI from Vault (required)."""
        if self._db_config is None:
            self._db_config = self.vault_client.get_database_config()
        
        if self._db_config and self._db_config.get('url'):
            logger.info("Using database configuration from Vault")
            return self._db_config['url']
        
        raise RuntimeError("Database configuration not available from Vault")

    def get_s3_client(self):
        """Get S3 client instance with AWS Roles Anywhere authentication from Vault."""
        if self._s3_client is None:
            
            # Get S3 configuration from Vault
            s3_config = self.vault_client.get_s3_config()
            
            self._s3_client = S3Client(
                region=s3_config['region'],
                bucket_name=s3_config['bucket'],
                trust_anchor_arn=s3_config['trust_anchor_arn'],
                profile_arn=s3_config['profile_arn'],
                role_arn=s3_config['role_arn'],
                certificate_pem=s3_config['certificate'],
                private_key_pem=s3_config['private_key']
            )
            
            if not self._s3_client:
                raise RuntimeError("Failed to initialize S3 client")
            
            logger.info("S3 client initialized with AWS Roles Anywhere credentials from Vault")
        return self._s3_client

    def get_user_password(self, username: str) -> str:
        """Get default password for a user from Vault.
        
        Args:
            username: Username (admin, alice, moderator)
            
        Returns:
            Default password for the user
        """
        password_key = f'{username.lower()}_password'
        password = self.app_secrets.get(password_key)
        if not password:
            raise RuntimeError(f"Password for user '{username}' not found in Vault at key '{password_key}'")
        return password


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


def get_config() -> Config:
    """Get configuration based on environment."""
    env = os.environ.get('FLASK_ENV')
    if not env:
        raise RuntimeError("FLASK_ENV environment variable is required (production or development)")
    if env == 'production':
        return ProductionConfig()
    elif env == 'development':
        return DevelopmentConfig()
    else:
        raise RuntimeError(f"Invalid FLASK_ENV value: {env}. Must be 'production' or 'development'")