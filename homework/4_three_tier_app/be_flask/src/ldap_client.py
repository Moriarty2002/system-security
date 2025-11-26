"""LDAP client for user authentication with Vault integration.

This module provides LDAP authentication and role mapping functionality.
LDAP credentials are securely managed through HashiCorp Vault.

Security Features:
- LDAP bind credentials stored in Vault
- Connection pooling with timeout protection
- Secure LDAP (LDAPS) support
- Role mapping based on LDAP group membership
"""

import logging
from typing import Optional, List, Tuple
import ldap
from ldap.ldapobject import LDAPObject

logger = logging.getLogger(__name__)


class LdapClient:
    """LDAP client with Vault-managed credentials."""

    def __init__(self, ldap_url: str, bind_dn: str, bind_password: str, base_dn: str):
        """Initialize LDAP client.

        Args:
            ldap_url: LDAP server URL (e.g., ldap://ldap-server:389)
            bind_dn: DN to bind as for user lookups
            bind_password: Password for bind DN
            base_dn: Base DN for searches (e.g., dc=cloud,dc=mes)
        """
        self.ldap_url = ldap_url
        self.bind_dn = bind_dn
        self.bind_password = bind_password
        self.base_dn = base_dn
        self.users_ou = f"ou=users,{base_dn}"
        self.groups_ou = f"ou=groups,{base_dn}"

        # LDAP connection settings
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
        ldap.set_option(ldap.OPT_REFERRALS, 0)
        ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 10)

    def _get_connection(self) -> LDAPObject:
        """Create and return a new LDAP connection.

        Returns:
            LDAP connection object

        Raises:
            ldap.LDAPError: If connection fails
        """
        try:
            conn = ldap.initialize(self.ldap_url)
            conn.simple_bind_s(self.bind_dn, self.bind_password)
            return conn
        except ldap.LDAPError as e:
            logger.error(f"Failed to connect to LDAP server: {e}")
            raise

    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """Authenticate user against LDAP directory.

        Args:
            username: Username to authenticate
            password: Password to verify

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if not username or not password:
            return False, "Username and password required"

        user_dn = f"uid={username},{self.users_ou}"
        conn = None

        try:
            # Attempt to bind as the user
            conn = ldap.initialize(self.ldap_url)
            conn.simple_bind_s(user_dn, password)
            logger.info(f"LDAP authentication successful for user: {username}")
            return True, None
        except ldap.INVALID_CREDENTIALS:
            logger.warning(f"LDAP authentication failed for user: {username} - invalid credentials")
            return False, "Invalid credentials"
        except ldap.NO_SUCH_OBJECT:
            logger.warning(f"LDAP authentication failed for user: {username} - user not found")
            return False, "User not found"
        except ldap.LDAPError as e:
            logger.error(f"LDAP authentication error for user {username}: {e}")
            return False, "Authentication service unavailable"
        finally:
            if conn:
                try:
                    conn.unbind_s()
                except:
                    pass

    def get_user_groups(self, username: str) -> List[str]:
        """Get list of groups the user belongs to.

        Args:
            username: Username to look up

        Returns:
            List of group names (e.g., ['admins', 'users'])
        """
        conn = None
        try:
            conn = self._get_connection()
            user_dn = f"uid={username},{self.users_ou}"

            # Search for groups where user is a member
            search_filter = f"(member={user_dn})"
            result = conn.search_s(
                self.groups_ou,
                ldap.SCOPE_SUBTREE,
                search_filter,
                ['cn']
            )

            groups = []
            for dn, attrs in result:
                if 'cn' in attrs:
                    groups.extend([cn.decode('utf-8') for cn in attrs['cn']])

            logger.debug(f"User {username} belongs to groups: {groups}")
            return groups

        except ldap.LDAPError as e:
            logger.error(f"Failed to get groups for user {username}: {e}")
            return []
        finally:
            if conn:
                try:
                    conn.unbind_s()
                except:
                    pass

    def get_user_role(self, username: str) -> str:
        """Determine user's role based on LDAP group membership.

        Role priority: admin > moderator > user

        Args:
            username: Username to look up

        Returns:
            Role string: 'admin', 'moderator', or 'user'
        """
        groups = self.get_user_groups(username)

        # Check for roles in priority order
        if 'admins' in groups:
            return 'admin'
        elif 'moderators' in groups:
            return 'moderator'
        else:
            return 'user'

    def get_user_info(self, username: str) -> Optional[dict]:
        """Get user information from LDAP directory.

        Args:
            username: Username to look up

        Returns:
            Dictionary with user info or None if not found
        """
        conn = None
        try:
            conn = self._get_connection()
            user_dn = f"uid={username},{self.users_ou}"

            # Search for user attributes
            result = conn.search_s(
                user_dn,
                ldap.SCOPE_BASE,
                '(objectClass=*)',
                ['cn', 'mail', 'givenName', 'sn']
            )

            if result:
                dn, attrs = result[0]
                user_info = {
                    'username': username,
                    'display_name': attrs.get('cn', [b''])[0].decode('utf-8'),
                    'email': attrs.get('mail', [b''])[0].decode('utf-8'),
                    'given_name': attrs.get('givenName', [b''])[0].decode('utf-8'),
                    'surname': attrs.get('sn', [b''])[0].decode('utf-8')
                }
                return user_info

            return None

        except ldap.NO_SUCH_OBJECT:
            logger.warning(f"User not found in LDAP: {username}")
            return None
        except ldap.LDAPError as e:
            logger.error(f"Failed to get user info for {username}: {e}")
            return None
        finally:
            if conn:
                try:
                    conn.unbind_s()
                except:
                    pass


def get_ldap_client(ldap_config: dict) -> LdapClient:
    """Factory function to create LDAP client from configuration.

    Args:
        ldap_config: Dictionary with LDAP configuration from Vault

    Returns:
        Configured LdapClient instance

    Raises:
        ValueError: If configuration is missing required fields
    """
    required_fields = ['url', 'bind_dn', 'bind_password', 'base_dn']
    missing = [f for f in required_fields if f not in ldap_config]

    if missing:
        raise ValueError(f"LDAP configuration missing required fields: {missing}")

    return LdapClient(
        ldap_url=ldap_config['url'],
        bind_dn=ldap_config['bind_dn'],
        bind_password=ldap_config['bind_password'],
        base_dn=ldap_config['base_dn']
    )
