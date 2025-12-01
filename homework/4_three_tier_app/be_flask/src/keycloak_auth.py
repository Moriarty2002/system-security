"""
Keycloak authentication module.

This module provides Keycloak token validation and user authentication.
All authentication is delegated to Keycloak - no password handling in the application.
"""

import logging
import requests
import os
from typing import Tuple, Dict, Optional
from functools import wraps
from flask import request, abort, current_app, g
import jwt
from jwt import PyJWKClient
import urllib3

from .models import db, UserProfile

logger = logging.getLogger(__name__)

# Disable SSL warnings for development with self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class KeycloakAuth:
    """Keycloak authentication helper."""
    
    def __init__(self, server_url: str, realm: str, client_id: str):
        """Initialize Keycloak authentication.
        
        Args:
            server_url: Keycloak server URL (e.g., http://keycloak:8080)
            realm: Keycloak realm name
            client_id: Client ID for this application
        """
        self.server_url = server_url.rstrip('/')
        self.realm = realm
        self.client_id = client_id
        self.realm_url = f"{self.server_url}/realms/{self.realm}"
        self.certs_url = f"{self.realm_url}/protocol/openid-connect/certs"
        
        # JWKS cache
        self.jwks_data = None
        # Control SSL verification via app config: set `KEYCLOAK_SKIP_VERIFY` to true to skip
        try:
            skip_verify = current_app.config.get('KEYCLOAK_SKIP_VERIFY', False)
        except RuntimeError:
            # If not in app context, default to verifying
            skip_verify = False

        self.use_ssl_verify = not bool(skip_verify)
        if not self.use_ssl_verify:
            logger.warning("SSL verification disabled for Keycloak connection (KEYCLOAK_SKIP_VERIFY=True)")
        
        logger.info(f"KeycloakAuth initialized for realm '{realm}' at {server_url}")
    
    def get_public_key(self, token: str) -> str:
        """Get the public key for token verification.
        
        Args:
            token: JWT token
            
        Returns:
            Public key string
        """
        try:
            # Fetch JWKS data if not cached
            if not self.jwks_data:
                # Fetch JWKS via requests; prefer system CA bundle if available
                verify_arg = self.use_ssl_verify
                if self.use_ssl_verify:
                    system_bundle = '/etc/ssl/certs/ca-certificates.crt'
                    if os.path.exists(system_bundle):
                        verify_arg = system_bundle

                response = requests.get(self.certs_url, timeout=10, verify=verify_arg)
                response.raise_for_status()
                self.jwks_data = response.json()
                logger.info(f"Successfully fetched JWKS from {self.certs_url}")
            
            # Get key ID from token header
            token_header = jwt.get_unverified_header(token)
            kid = token_header.get('kid')
            
            if not kid:
                raise ValueError("Token does not have a key ID (kid)")
            
            # Find matching key in JWKS
            for key in self.jwks_data.get('keys', []):
                if key.get('kid') == kid:
                    # Import the key
                    from jwt.algorithms import RSAAlgorithm
                    return RSAAlgorithm.from_jwk(key)
            
            raise ValueError(f"Key with kid '{kid}' not found in JWKS")
            
        except Exception as e:
            logger.error(f"Failed to get public key: {e}")
            raise
    
    def verify_token(self, token: str) -> Dict:
        """Verify and decode Keycloak JWT token.
        
        Args:
            token: JWT token from Authorization header
            
        Returns:
            Decoded token payload
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            # Get the signing key
            public_key = self.get_public_key(token)
            
            # Decode and verify the token
            # Note: Public clients may not have audience claim, so we verify manually if present
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                options={
                    'verify_signature': True,
                    'verify_aud': False,  # Verify manually for public clients
                    'verify_exp': True
                }
            )
            
            # Manual audience verification if present
            if 'aud' in payload:
                audiences = payload['aud'] if isinstance(payload['aud'], list) else [payload['aud']]
                # Accept if our client_id is in the audience OR if it's account (Keycloak default for public clients)
                if self.client_id not in audiences and 'account' not in audiences:
                    logger.warning(f"Token audience {audiences} doesn't match expected {self.client_id}")
                    raise jwt.InvalidAudienceError(f"Invalid audience: {audiences}")
            
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise
        except jwt.InvalidAudienceError:
            logger.warning("Invalid token audience")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise
    
    def extract_user_info(self, token_payload: Dict) -> Dict:
        """Extract user information from token payload.
        
        Args:
            token_payload: Decoded JWT payload
            
        Returns:
            Dict with user information (sub, username, email, roles)
        """
        # Extract user ID (subject)
        keycloak_id = token_payload.get('sub')
        
        # Extract username (preferred_username is standard in Keycloak)
        username = token_payload.get('preferred_username') or token_payload.get('email', '').split('@')[0]
        
        # Extract email
        email = token_payload.get('email')
        
        # Extract roles from realm_access or resource_access
        realm_roles = token_payload.get('realm_access', {}).get('roles', [])
        client_roles = token_payload.get('resource_access', {}).get(self.client_id, {}).get('roles', [])
        
        # Determine application role based on Keycloak roles
        role = 'user'  # default
        if 'admin' in realm_roles or 'admin' in client_roles:
            role = 'admin'
        elif 'moderator' in realm_roles or 'moderator' in client_roles:
            role = 'moderator'
        
        return {
            'keycloak_id': keycloak_id,
            'username': username,
            'email': email,
            'role': role,
            'realm_roles': realm_roles,
            'client_roles': client_roles
        }


    # --- Keycloak Admin helpers ---
    def _get_verify_arg(self):
        """Determine `verify` argument for requests (path or bool)."""
        verify_arg = self.use_ssl_verify
        if self.use_ssl_verify:
            system_bundle = '/etc/ssl/certs/ca-certificates.crt'
            if os.path.exists(system_bundle):
                verify_arg = system_bundle
        return verify_arg

    def get_admin_token(self) -> Optional[str]:
        """Obtain an admin access token using client credentials.

        Returns:
            access token string or None if client secret not configured.
        """
        try:
            # Use cached token if present and not expired isn't implemented here
            # Keep it simple: fetch a fresh token when needed
            client_secret = current_app.config.get('KEYCLOAK_CLIENT_SECRET_ADMIN')
            if not client_secret:
                raise RuntimeError('Keycloak client secret admin not configured (KEYCLOAK_CLIENT_SECRET_ADMIN required)')

            token_url = f"{self.realm_url}/protocol/openid-connect/token"
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': client_secret
            }
            resp = requests.post(token_url, data=data, timeout=10, verify=self._get_verify_arg())
            resp.raise_for_status()
            return resp.json().get('access_token')
        except Exception as e:
            logger.warning(f'Failed to obtain Keycloak admin token: {e}')
            return None

    def admin_get_user(self, keycloak_id: str) -> Optional[Dict]:
        """Fetch a user's representation from Keycloak Admin API by Keycloak ID.

        Returns:
            JSON user representation, or None if not found or admin access not available.
        """
        try:
            token = self.get_admin_token()
            if not token:
                return None

            headers = {'Authorization': 'Bearer ' + token}
            url = f"{self.server_url}/admin/realms/{self.realm}/users/{keycloak_id}"
            resp = requests.get(url, headers=headers, timeout=10, verify=self._get_verify_arg())
            if resp.status_code == 404:
                return None
            # If token expired/invalid, try to fetch a fresh token and retry once
            if resp.status_code == 401:
                token = self.get_admin_token()
                if not token:
                    return None
                headers = {'Authorization': 'Bearer ' + token}
                resp = requests.get(url, headers=headers, timeout=10, verify=self._get_verify_arg())

            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f'Failed to fetch user {keycloak_id} from Keycloak admin API: {e}')
            return None


def get_keycloak_auth() -> KeycloakAuth:
    """Get or create KeycloakAuth instance from app config.
    
    Returns:
        KeycloakAuth instance
    """
    if not hasattr(current_app, 'keycloak_auth'):
        server_url = current_app.config.get('KEYCLOAK_SERVER_URL')
        realm = current_app.config.get('KEYCLOAK_REALM')
        client_id = current_app.config.get('KEYCLOAK_CLIENT_ID')
        
        if not all([server_url, realm, client_id]):
            raise RuntimeError("Keycloak configuration is incomplete")
        
        current_app.keycloak_auth = KeycloakAuth(server_url, realm, client_id)
    
    return current_app.keycloak_auth


def get_admin_keycloak_auth() -> KeycloakAuth:
    """Get or create a KeycloakAuth instance configured with the admin/service-account client."""
    if not hasattr(current_app, 'keycloak_admin_auth'):
        server_url = current_app.config.get('KEYCLOAK_SERVER_URL')
        realm = current_app.config.get('KEYCLOAK_REALM')
        # Allow an explicit admin client id in config
        client_id = current_app.config.get('KEYCLOAK_CLIENT_ID_ADMIN')
        current_app.keycloak_admin_auth = KeycloakAuth(server_url, realm, client_id)

    return current_app.keycloak_admin_auth


def authenticate_user() -> Tuple[str, UserProfile]:
    """Authenticate request using Keycloak Bearer JWT token.
    
    Returns:
        Tuple of (username, user_profile_object)
        
    Raises:
        401: Missing or invalid authentication
        403: User not found or inactive
    """
    auth = request.headers.get('Authorization')
    if not auth or not auth.startswith('Bearer '):
        logger.warning("Missing or invalid Authorization header")
        abort(401, description='Missing authentication token')
    
    token = auth.split(' ', 1)[1].strip()
    
    try:
        # Verify token with Keycloak
        keycloak_auth = get_keycloak_auth()
        payload = keycloak_auth.verify_token(token)
        
        # Extract user information
        user_info = keycloak_auth.extract_user_info(payload)
        keycloak_id = user_info['keycloak_id']
        username = user_info['username']
        
        # Get or create user profile (keycloak_id and quota only)
        user_profile = UserProfile.query.filter_by(keycloak_id=keycloak_id).first()
        
        if not user_profile:
            # First time login - create user profile
            user_profile = UserProfile(
                keycloak_id=keycloak_id,
                quota=104857600  # 100MB default quota
            )
            db.session.add(user_profile)
            db.session.commit()
            logger.info(f"Created new user profile for {username} (Keycloak ID: {keycloak_id})")
        
        # Store user info in Flask g for access in request handlers
        # Username and role stored in g (from token), NOT in database
        # This ensures always-fresh values and automatic sync with Keycloak
        g.user_info = user_info
        g.user_profile = user_profile
        g.username = username  # From token, always fresh
        g.user_role = user_info['role']  # From token, always fresh
        
        return username, user_profile
        
    except jwt.ExpiredSignatureError:
        logger.warning("Attempt to use expired JWT token")
        abort(401, description='Token expired')
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        abort(401, description='Invalid token')
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        abort(500, description='Authentication error')


def require_role(required_role: str):
    """Decorator to require a specific role.
    
    Args:
        required_role: Required role ('user', 'moderator', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ensure user is authenticated
            username, _ = authenticate_user()
            
            # Get role from Flask g (fresh from Keycloak token)
            user_role = g.user_role
            
            # Check role hierarchy
            role_hierarchy = {'user': 0, 'moderator': 1, 'admin': 2}
            user_level = role_hierarchy.get(user_role, 0)
            required_level = role_hierarchy.get(required_role, 0)
            
            if user_level < required_level:
                logger.warning(f"User {username} (role={user_role}) attempted to access {required_role}-only resource")
                abort(403, description=f'{required_role} role required')
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin() -> None:
    """Check if user has admin privileges.
    
    Role is fetched from Flask g (set by authenticate_user from Keycloak token).
        
    Raises:
        403: User is not admin
    """
    # Get role from Flask g (fresh from Keycloak token)
    user_role = g.user_role
    if user_role != 'admin':
        abort(403, description='Admin role required')
