# Access Control Procedures (AC-1)

## Document Control
- **Version**: 1.0
- **Effective Date**: 16 December 2025
- **Review Date**: December 2026
- **Owner**: Marcello Esposito

## 1. Purpose
These procedures implement the Access Control Policy (AC-1) providing step-by-step guidance for managing access control in the Secure File Storage Service.

## 2. User Access Procedures

### 2.1 New User Account Creation
1. Administrator logs into Keycloak Admin Console (http://localhost:8080)
2. Navigate to realm: `mes_local_cloud`
3. Users → Add User
4. Set username, email, enable account
5. Credentials → Set Password (temporary or permanent)
6. Role Mappings → Assign role:
   - Realm roles: `admin`, `moderator`, or leave as default `user`
   - Client roles (mes-file-storage): `admin`, `moderator`, or `user`
7. User profile automatically created in application on first login

**Implementation**: [keycloak-infrastructure/scripts/init-keycloak.sh](../../../keycloak-infrastructure/scripts/init-keycloak.sh)

### 2.2 Role Assignment/Modification
1. Login to Keycloak Admin Console
2. Navigate to Users → Select user
3. Role Mappings tab
4. Add/Remove realm or client roles
5. Changes effective on next token refresh (max 5 minutes)

**Note**: Roles are validated on every API request - no cache refresh required

### 2.3 User Access Revocation
1. Keycloak Admin Console → Users → Select user
2. Disable user account (toggle "Enabled" off)
3. Optionally: Delete user (Actions → Delete)
4. Active tokens remain valid until expiry (max 5 minutes)
5. To force immediate logout: Sessions tab → Logout all sessions

## 3. Service Account Access Procedures

### 3.1 Create Vault AppRole for New Service

**Script**: [vault/scripts/setup-vault-app.sh](../vault/scripts/setup-vault-app.sh)

Steps performed by script:
1. Enable AppRole auth method (if not enabled)
2. Create service-specific policy:
   ```hcl
   path "secret/data/mes_local_cloud/*" {
     capabilities = ["read", "list"]
   }
   ```
3. Create AppRole with policy attached:
   ```bash
   vault write auth/approle/role/mes-flask-app \
     token_ttl=20m \
     token_max_ttl=30m \
     policies="mes-flask-policy"
   ```
4. Retrieve role_id and secret_id
5. Store credentials in `.env` file:
   ```
   VAULT_ROLE_ID=<role_id>
   VAULT_SECRET_ID=<secret_id>
   ```

### 3.2 Backend Service Authentication to Vault

**Implementation**: [be_flask/src/vault_client.py](../be_flask/src/vault_client.py)

Flow:
1. Backend reads `VAULT_ROLE_ID` and `VAULT_SECRET_ID` from environment
2. POST to Vault AppRole endpoint:
   ```
   POST https://vault:8200/v1/auth/approle/login
   {
     "role_id": "<role_id>",
     "secret_id": "<secret_id>"
   }
   ```
3. Vault returns client_token (20-minute TTL)
4. Backend uses token for secret retrieval:
   ```
   GET https://vault:8200/v1/secret/data/mes_local_cloud/database
   X-Vault-Token: <client_token>
   ```
5. Token automatically renewed before expiry

### 3.3 Apache Certificate Renewal from Vault PKI

**Implementation**: [apache/scripts/fetch-vault-cert.sh](../apache/scripts/fetch-vault-cert.sh)

Process (automated via entrypoint):
1. Apache container authenticates to Vault using AppRole
2. Requests certificate from PKI engine:
   ```
   POST https://vault:8200/v1/pki_shared/issue/apache-role
   {
     "common_name": "localhost",
     "ttl": "24h"
   }
   ```
3. Vault issues certificate + private key
4. Apache stores in tmpfs (in-memory, not persisted)
5. Apache reloaded with new certificate
6. Certificate auto-renewed every 12 hours

## 4. Authorization Procedures

### 4.1 API Request Authorization Flow

**Implementation**: [be_flask/src/keycloak_auth.py](../be_flask/src/keycloak_auth.py)

For each API request:
1. Extract Bearer token from Authorization header
2. Validate token signature using Keycloak public key (RS256)
3. Check token expiry
4. Extract user claims: `preferred_username`, `realm_roles`, `resource_access`
5. Determine user role:
   - `admin` if "admin" in realm_roles or client_roles
   - `moderator` if "moderator" in realm_roles or client_roles
   - `user` otherwise
6. Store user info in Flask `g` context
7. Execute endpoint-specific authorization checks:
   - `@require_admin()` - admin only
   - `@require_admin_moderator()` - admin or moderator
   - Custom logic for resource ownership

Example protected endpoint:
```python
@app.route('/api/admin/users')
@authenticate_user
def list_users():
    require_admin_moderator()  # Enforces admin/moderator access
    # ... implementation
```

### 4.2 File Access Authorization

Rules:
- **Admin**: Access all files
- **Moderator**: Access all files
- **User**: Access only own files

Implementation:
```python
# Check file ownership
file_owner = get_file_owner(file_id)
if g.user_role not in ['admin', 'moderator'] and file_owner != g.username:
    abort(403, 'Access denied')
```

## 5. Network Access Control

### 5.1 Container Network Assignment

Defined in [docker-compose.yaml](../docker-compose.yaml):

- **apache-fe**: `app_net`, `shared_vault_net`
- **backend**: `app_net`, `db_net`, `shared_vault_net`
- **db**: `db_net` only
- **minio**: `storage_net`, `app_net`
- **ldap**: `ldap_net` (if used)

Services cannot communicate unless on shared network.

### 5.2 Port Exposure

Only essential ports exposed to host:
- Apache: 80, 443 (public HTTPS access)
- Vault: 127.0.0.1:8200 (localhost only)
- Keycloak: 8080 (admin access, should be restricted in production)

Internal services (database, backend) not exposed to host.

## 6. Container Capability Management

### 6.1 Standard Capability Set

All containers follow least privilege:
```yaml
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE  # Bind privileged ports (80, 443)
  - SETGID            # Change GID
  - SETUID            # Change UID
  # Service-specific additions only
```

Example exceptions:
- Vault: Add `IPC_LOCK` for memory locking
- Database: Add `DAC_OVERRIDE` for file access

### 6.2 Read-Only Filesystem Enforcement

Containers run with `read_only: true` where possible:
- Config files mounted read-only
- Writable areas provided via tmpfs (in-memory)
- Example:
  ```yaml
  volumes:
    - ./config:ro
  tmpfs:
    - /tmp:mode=1777,size=50M
  ```

## 7. Audit and Monitoring Procedures

### 7.1 Review Access Logs
```bash
# View backend authentication logs
docker logs flask_be | grep "authentication"

# View Vault audit log
docker exec shared_vault_server cat /vault/logs/audit.log

# View Keycloak events
# Admin Console → Realm → Events → Login Events
```

### 7.2 Review User Access Rights (Quarterly)
1. Export user list from Keycloak
2. Validate role assignments match job functions
3. Remove inactive accounts (>90 days no login)
4. Document review in access control audit log

### 7.3 Security Incident Response
If unauthorized access detected:
1. Immediately disable affected user account in Keycloak
2. Logout all sessions for user
3. Review Vault and application logs for accessed resources
4. Rotate secrets if compromised
5. Document incident and remediation

## 8. Maintenance Procedures

### 8.1 Vault Secret Rotation
```bash
# Update database password
docker exec shared_vault_server vault kv put secret/mes_local_cloud/database \
  POSTGRES_PASSWORD="<new-password>"

# Restart backend to fetch new secret
docker restart flask_be
```

### 8.2 AppRole Secret Rotation
```bash
vault write -f auth/approle/role/mes-flask-app/secret-id
# Update VAULT_SECRET_ID in .env
# Restart affected service
```

### 8.3 Certificate Rotation
Automatic via Vault PKI - certificates renewed every 12 hours by Apache entrypoint script. Manual rotation not required.

## 9. Related Procedures
- IA-1: Identification and Authentication Procedures
- SC-1: System and Communications Protection Procedures
- AC-20: Use of External Systems
