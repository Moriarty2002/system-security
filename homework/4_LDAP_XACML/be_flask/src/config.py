import os
from typing import Optional

# Optional Vault support. If `VAULT_ADDR` is set (and `hvac` is installed),
# the app will attempt to authenticate (via token or AppRole) and load
# secrets from the KV v2 path `secret/flask`. Loaded secrets are exported
# into `os.environ` only when the corresponding env var is not already set.
try:
    import hvac
except Exception:
    hvac = None


def _load_secrets_from_vault() -> None:
    vault_addr = os.environ.get('VAULT_ADDR')
    if not vault_addr or hvac is None:
        return

    token = os.environ.get('VAULT_TOKEN')
    client = hvac.Client(url=vault_addr, token=token)

    # If token auth failed, try AppRole if credentials are present
    if not client.is_authenticated():
        role_id = os.environ.get('VAULT_ROLE_ID')
        secret_id = os.environ.get('VAULT_SECRET_ID')
        if role_id and secret_id:
            try:
                client.auth.approle.login(role_id=role_id, secret_id=secret_id)
            except Exception:
                return

    if not client.is_authenticated():
        return

    try:
        # Read KV V2 secret at `secret/flask` and flatten into env
        secret = client.secrets.kv.v2.read_secret_version(path='flask')
        data = secret.get('data', {}).get('data', {}) or {}
        for k, v in data.items():
            # do not override existing environment variables
            if os.environ.get(k) is None and v is not None:
                os.environ[k] = str(v)
    except Exception:
        # Ignore vault errors and fall back to environment variables
        return


_load_secrets_from_vault()


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
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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