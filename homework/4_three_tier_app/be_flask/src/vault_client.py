"""Vault client for secrets management with AppRole authentication."""

import os
import logging
import time
from typing import Dict, Optional, Any
from threading import Lock
import urllib3
import hvac
from hvac.exceptions import VaultError, InvalidPath


logger = logging.getLogger(__name__)


class VaultClient:
    """Thread-safe Vault client with caching and automatic token renewal."""

    def __init__(self):
        """Initialize Vault client with AppRole authentication."""
        self.vault_addr = os.environ.get('VAULT_ADDR')
        self.role_id = os.environ.get('VAULT_ROLE_ID')
        self.secret_id = os.environ.get('VAULT_SECRET_ID')
        
        if not self.vault_addr:
            raise RuntimeError("VAULT_ADDR environment variable is required")
        # Skip TLS verification for self-signed certificates (dev only)
        # When VAULT_SKIP_VERIFY=1, we want verify=False
        self.verify_tls = os.environ.get('VAULT_SKIP_VERIFY', '0') == '0'
        
        # Disable SSL warnings when skipping verification
        if not self.verify_tls:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        self.client: Optional[hvac.Client] = None
        self.token_expiry: float = 0
        self.cache: Dict[str, tuple] = {}  # {path: (data, expiry_time)}
        self.cache_ttl = 300  # Cache for 5 minutes
        self.lock = Lock()
        
        self._enabled = self._check_vault_enabled()
        
        if self._enabled:
            self._authenticate()
        else:
            logger.error("Vault is not enabled. Application requires Vault for secrets management.")
            raise RuntimeError("Vault is not enabled. Application requires Vault for secrets management.")

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
            client = hvac.Client(url=self.vault_addr, verify=self.verify_tls)
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
            self.client = hvac.Client(url=self.vault_addr, verify=self.verify_tls)
            
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
        secrets = self._read_secret('mes_local_cloud/app/flask')
        
        if secrets:
            return {
                'jwt_secret': secrets.get('jwt_secret'),
                'admin_password': secrets.get('admin_password'),
                'alice_password': secrets.get('alice_password'),
                'moderator_password': secrets.get('moderator_password'),
                'CA_chain': secrets.get('CA_chain') or secrets.get('ca_chain')
            }
        
        logger.error("Failed to retrieve app secrets from Vault")
        raise RuntimeError("Application secrets not available from Vault. Ensure Vault is configured and accessible.")

    def get_database_config(self) -> Dict[str, str]:
        """Get database configuration from Vault.
        
        Returns:
            Dictionary containing database connection parameters
        """
        from urllib.parse import quote_plus
        
        db_secrets = self._read_secret('mes_local_cloud/database/postgres')
        
        if db_secrets:
            username = db_secrets.get('username')
            password = db_secrets.get('password')
            database = db_secrets.get('database')
            host = db_secrets.get('host')
            port = db_secrets.get('port')
            
            # Validate all required fields are present
            if not all([username, password, database, host, port]):
                raise RuntimeError("Incomplete database configuration in Vault. Required: username, password, database, host, port")
            
            # URL-encode credentials to handle special characters
            username_encoded = quote_plus(username)
            password_encoded = quote_plus(password)
            
            return {
                'username': username,
                'password': password,
                'database': database,
                'host': host,
                'port': port,
                'url': f"postgresql://{username_encoded}:{password_encoded}@{host}:{port}/{database}"
            }
        
        logger.error("Failed to retrieve database config from Vault")
        raise RuntimeError("Database configuration not available from Vault. Ensure Vault is configured and accessible.")

    def get_minio_config(self) -> Dict[str, str]:
        """Get MinIO configuration from Vault.
        
        Returns:
            Dictionary containing MinIO connection parameters
        """
        minio_secrets = self._read_secret('mes_local_cloud/minio')
        
        if minio_secrets:
            access_key = minio_secrets.get('access_key')
            secret_key = minio_secrets.get('secret_key')
            endpoint = minio_secrets.get('endpoint')
            bucket = minio_secrets.get('bucket')
            use_ssl = minio_secrets.get('use_ssl')
            
            # Validate all required fields are present
            if not all([access_key, secret_key, endpoint, bucket]):
                raise RuntimeError("Incomplete MinIO configuration in Vault. Required: access_key, secret_key, endpoint, bucket")
            
            return {
                'access_key': access_key,
                'secret_key': secret_key,
                'endpoint': endpoint,
                'bucket': bucket,
                'use_ssl': use_ssl if isinstance(use_ssl, bool) else str(use_ssl).lower() == 'true'
            }
        
        logger.error("Failed to retrieve MinIO config from Vault")
        raise RuntimeError("MinIO configuration not available from Vault. Ensure Vault is configured and accessible.")
    
    def get_s3_config(self) -> Dict[str, str]:
        """Get AWS S3 configuration with Roles Anywhere credentials from Vault.
        
        Returns:
            Dictionary containing S3 connection parameters and credentials
        """
        s3_secrets = self._read_secret('mes_local_cloud/app/flask')
        
        if s3_secrets:
            certificate = s3_secrets.get('flask_aws_s3_certificate')
            private_key = s3_secrets.get('flask_aws_s3_key')
            region = s3_secrets.get('aws_region')
            bucket = s3_secrets.get('aws_s3_bucket')
            trust_anchor_arn = s3_secrets.get('aws_trust_anchor_arn')
            profile_arn = s3_secrets.get('aws_profile_arn')
            role_arn = s3_secrets.get('aws_role_arn')
            
            # Validate all required fields are present
            if not all([certificate, private_key, region, bucket, trust_anchor_arn, profile_arn, role_arn]):
                raise RuntimeError(
                    "Incomplete S3 configuration in Vault. Required: flask_aws_s3_certificate, "
                    "flask_aws_s3_key, aws_region, aws_s3_bucket, aws_trust_anchor_arn, "
                    "aws_profile_arn, aws_role_arn"
                )
            
            return {
                'certificate': certificate,
                'private_key': private_key,
                'region': region,
                'bucket': bucket,
                'trust_anchor_arn': trust_anchor_arn,
                'profile_arn': profile_arn,
                'role_arn': role_arn
            }
        
        logger.error("Failed to retrieve S3 config from Vault")
        raise RuntimeError("S3 configuration not available from Vault. Ensure Vault is configured and accessible.")
    
    def get_keycloak_config(self) -> Optional[Dict[str, str]]:
        """Get Keycloak configuration from Vault.
        
        Returns:
            Dictionary containing Keycloak connection parameters, or None if not found
        """
        keycloak_secrets = self._read_secret('keycloak/client')

        # Return the raw stored map if present. Do not fabricate defaults here.
        if keycloak_secrets:
            return keycloak_secrets

        return None

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
