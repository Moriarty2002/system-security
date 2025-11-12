import os


class Config:
    """Base configuration class."""

    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # LDAP Configuration (for future LDAP integration)
    LDAP_ENABLED: bool = os.environ.get('LDAP_ENABLED', 'false').lower() == 'true'
    LDAP_SERVER: str = os.environ.get('LDAP_SERVER', 'ldap://localhost:389')
    LDAP_BASE_DN: str = os.environ.get('LDAP_BASE_DN', 'dc=example,dc=com')
    LDAP_BIND_USER: str = os.environ.get('LDAP_BIND_USER', '')
    LDAP_BIND_PASSWORD: str = os.environ.get('LDAP_BIND_PASSWORD', '')
    LDAP_USER_SEARCH_FILTER: str = os.environ.get('LDAP_USER_SEARCH_FILTER', '(uid={username})')
    LDAP_USER_DN_ATTRIBUTE: str = os.environ.get('LDAP_USER_DN_ATTRIBUTE', 'dn')
    LDAP_USER_ATTRIBUTES: dict = {
        'username': os.environ.get('LDAP_USERNAME_ATTR', 'uid'),
        'email': os.environ.get('LDAP_EMAIL_ATTR', 'mail'),
        'role': os.environ.get('LDAP_ROLE_ATTR', 'employeeType')
    }

    # XACML Configuration (for future XACML integration)
    XACML_ENABLED: bool = os.environ.get('XACML_ENABLED', 'false').lower() == 'true'
    XACML_PDP_URL: str = os.environ.get('XACML_PDP_URL', 'http://localhost:8080/pdp')
    XACML_POLICY_FILE: str = os.environ.get('XACML_POLICY_FILE', '/app/policies/default-policy.xml')
    XACML_REQUEST_TIMEOUT: int = int(os.environ.get('XACML_REQUEST_TIMEOUT', '30'))

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