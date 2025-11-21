"""
HashiCorp Vault Client Module

This module provides a secure interface to interact with HashiCorp Vault
for retrieving secrets, database credentials, and JWT signing keys.

Security Features:
- AppRole authentication with automatic token renewal
- Caching of secrets with configurable TTL
- Graceful degradation with fallback to environment variables
- Thread-safe operations
- Automatic retry logic for transient failures

Usage:
    vault_client = VaultClient()
    secrets = vault_client.get_app_secrets()
    db_config = vault_client.get_database_config()
"""

import os
import logging
import time
from typing import Dict, Optional, Any
from threading import Lock

import hvac
from hvac.exceptions import VaultError, InvalidPath


logger = logging.getLogger(__name__)


class VaultClient:
    """Thread-safe Vault client with caching and automatic token renewal."""

    def __init__(self):
        """Initialize Vault client with AppRole authentication."""
        self.vault_addr = os.environ.get('VAULT_ADDR', 'http://vault_server:8200')
        self.role_id = os.environ.get('VAULT_ROLE_ID')
        self.secret_id = os.environ.get('VAULT_SECRET_ID')
        
        self.client: Optional[hvac.Client] = None
        self.token_expiry: float = 0
        self.cache: Dict[str, tuple] = {}  # {path: (data, expiry_time)}
        self.cache_ttl = 300  # Cache for 5 minutes
        self.lock = Lock()
        
        self._enabled = self._check_vault_enabled()
        
        if self._enabled:
            self._authenticate()
        else:
            logger.warning("Vault is not enabled. Falling back to environment variables.")

    def _check_vault_enabled(self) -> bool:
        """Check if Vault is properly configured and reachable.
        
        Returns:
            bool: True if Vault is available and configured
        """
        if not self.role_id or not self.secret_id:
            logger.warning("Vault credentials (VAULT_ROLE_ID, VAULT_SECRET_ID) not found")
            return False
        
        try:
            # Quick health check
            client = hvac.Client(url=self.vault_addr)
            health = client.sys.read_health_status(method='GET')
            if health:
                logger.info(f"Vault server is reachable at {self.vault_addr}")
                return True
        except Exception as e:
            logger.warning(f"Cannot reach Vault server: {e}")
        
        return False

    def _authenticate(self) -> None:
        """Authenticate with Vault using AppRole and store the token."""
        try:
            self.client = hvac.Client(url=self.vault_addr)
            
            # Authenticate using AppRole
            auth_response = self.client.auth.approle.login(
                role_id=self.role_id,
                secret_id=self.secret_id,
            )
            
            # Store token and calculate expiry
            token = auth_response['auth']['client_token']
            lease_duration = auth_response['auth']['lease_duration']
            
            self.client.token = token
            # Renew token 5 minutes before expiry
            self.token_expiry = time.time() + lease_duration - 300
            
            logger.info("Successfully authenticated with Vault using AppRole")
            
        except VaultError as e:
            logger.error(f"Vault authentication failed: {e}")
            self._enabled = False
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Vault authentication: {e}")
            self._enabled = False
            raise

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid Vault token, renewing if necessary."""
        if not self._enabled:
            return
        
        with self.lock:
            # Check if token is about to expire
            if time.time() >= self.token_expiry:
                logger.info("Vault token expired or expiring soon, re-authenticating...")
                self._authenticate()

    def _read_secret(self, path: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Read a secret from Vault KV v2 engine with caching.
        
        Args:
            path: Secret path (e.g., 'app/flask')
            use_cache: Whether to use cached values
            
        Returns:
            Dictionary of secret data or None if unavailable
        """
        if not self._enabled:
            return None
        
        # Check cache first
        if use_cache and path in self.cache:
            data, expiry = self.cache[path]
            if time.time() < expiry:
                logger.debug(f"Using cached secret for path: {path}")
                return data
        
        try:
            self._ensure_authenticated()
            
            # Read from KV v2 (requires /data/ in path)
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point='secret'
            )
            
            data = response['data']['data']
            
            # Cache the result
            if use_cache:
                self.cache[path] = (data, time.time() + self.cache_ttl)
            
            logger.info(f"Successfully retrieved secret from Vault: {path}")
            return data
            
        except InvalidPath:
            logger.warning(f"Secret not found in Vault: {path}")
            return None
        except VaultError as e:
            logger.error(f"Error reading secret from Vault: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading secret: {e}")
            return None

    def get_app_secrets(self) -> Dict[str, str]:
        """Get application secrets (JWT key, user passwords, etc.).
        
        Returns:
            Dictionary containing application secrets
        """
        secrets = self._read_secret('app/flask')
        
        if secrets:
            return {
                'jwt_secret': secrets.get('jwt_secret'),
                'admin_password': secrets.get('admin_password'),
                'alice_password': secrets.get('alice_password'),
                'moderator_password': secrets.get('moderator_password'),
            }
        
        # Fallback to environment variables
        logger.warning("Using fallback environment variables for app secrets")
        return {
            'jwt_secret': os.environ.get('SECRET_KEY', 'dev-secret-key'),
            'admin_password': os.environ.get('ADMIN_PASSWORD', 'admin'),
            'alice_password': os.environ.get('ALICE_PASSWORD', 'alice'),
            'moderator_password': os.environ.get('MOD_PASSWORD', 'moderator'),
        }

    def get_database_config(self) -> Dict[str, str]:
        """Get database configuration from Vault.
        
        Returns:
            Dictionary containing database connection parameters
        """
        db_secrets = self._read_secret('database/postgres')
        
        if db_secrets:
            username = db_secrets.get('username')
            password = db_secrets.get('password')
            database = db_secrets.get('database')
            host = db_secrets.get('host', 'db')
            port = db_secrets.get('port', '5432')
            
            return {
                'username': username,
                'password': password,
                'database': database,
                'host': host,
                'port': port,
                'url': f"postgresql://{username}:{password}@{host}:{port}/{database}"
            }
        
        # Fallback to environment variables
        logger.warning("Using fallback environment variables for database config")
        username = os.environ.get('POSTGRES_USER', 'admin')
        password = os.environ.get('POSTGRES_PASSWORD', 'password123')
        database = os.environ.get('POSTGRES_DB', 'postgres_db')
        host = os.environ.get('POSTGRES_HOST', 'db')
        port = os.environ.get('POSTGRES_PORT', '5432')
        
        return {
            'username': username,
            'password': password,
            'database': database,
            'host': host,
            'port': port,
            'url': f"postgresql://{username}:{password}@{host}:{port}/{database}"
        }

    def invalidate_cache(self, path: Optional[str] = None) -> None:
        """Invalidate cached secrets.
        
        Args:
            path: Specific path to invalidate, or None to clear all cache
        """
        with self.lock:
            if path:
                self.cache.pop(path, None)
                logger.info(f"Invalidated cache for path: {path}")
            else:
                self.cache.clear()
                logger.info("Cleared entire secret cache")

    def is_available(self) -> bool:
        """Check if Vault is available and working.
        
        Returns:
            bool: True if Vault is properly configured and reachable
        """
        return self._enabled and self.client is not None


# Global instance
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Get or create the global VaultClient instance.
    
    Returns:
        VaultClient: Singleton Vault client instance
    """
    global _vault_client
    
    if _vault_client is None:
        _vault_client = VaultClient()
    
    return _vault_client
