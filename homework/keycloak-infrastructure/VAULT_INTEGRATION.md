# Keycloak Infrastructure - Vault Integration

This document explains how Keycloak integrates with HashiCorp Vault for secure credential management.

## Overview

The Keycloak infrastructure fetches all sensitive credentials from Vault at startup, following security best practices:

- **Database credentials** (username, password) stored in Vault
- **Admin credentials** (username, password) stored in Vault
- **TLS certificates** automatically generated from Vault PKI (shared with Apache)
- **AppRole authentication** for secure Vault access
- **No hardcoded secrets** in configuration files
- **Automatic secret rotation** support
- **Same CA as Apache** - unified certificate management

## Architecture

```
┌─────────────────────┐
│   Keycloak Server   │
│                     │
│  1. Authenticate    │──────┐
│     with AppRole    │      │
│                     │      ▼
│  2. Fetch Secrets   │  ┌──────────────┐
│     from Vault      │──│  Vault Server│
│                     │  └──────────────┘
│  3. Generate TLS    │      │
│     Certificate     │◄─────┤ Secrets:
│     (pki_localhost) │      │ - DB credentials
│                     │      │ - Admin credentials
│  4. Start with      │      │ - TLS certificates
│     retrieved creds │      │   (shared PKI with Apache)
└─────────────────────┘      │
          │                  │
          ▼                  │
┌─────────────────────┐      │
│  PostgreSQL (DB)    │◄─────┘
└─────────────────────┘
```

## Components

### 1. Vault Secrets

Secrets are stored in Vault's KV store:

```
secret/keycloak/database
  - username: keycloak
  - password: [auto-generated 32-char password]

secret/keycloak/admin
  - username: admin
  - password: [auto-generated 32-char password]

secret/keycloak/client
  - server_url: http://shared-keycloak-server:8080
  - realm: mes-local-cloud
  - client_id: mes-local-cloud-api            # browser-facing client
  - client_secret: <browser-client-secret>
  - client_id_admin: mes-local-cloud-admin-queries    # admin/service-account client
  - client_secret_admin: <admin-client-secret>
```

### 2. Vault AppRole

An AppRole is configured specifically for Keycloak:

- **Role Name**: `keycloak`
- **Policy**: `keycloak-policy` (read-only access to keycloak secrets)
- **Token TTL**: 1 hour
- **Token Max TTL**: 4 hours

### 3. Custom Entrypoint

`scripts/keycloak-entrypoint.sh` handles the Vault integration:

1. Validates `VAULT_ROLE_ID` and `VAULT_SECRET_ID` environment variables
2. Authenticates with Vault using AppRole
3. Fetches database and admin credentials
4. Generates TLS certificate from `pki_localhost` (shared with Apache)
5. Checks certificate expiration (auto-renews if < 7 days remaining)
6. Exports secrets as environment variables
7. Starts Keycloak with the official entrypoint

### 4. Custom Docker Image

The Dockerfile extends the official Keycloak image with:

- **Vault CLI** for secure secret retrieval
- **jq** for JSON processing (used by scripts)
- **Custom entrypoint** for Vault integration

## Setup Process

### Initial Setup

1. **Start Vault Infrastructure**:
   ```bash
   cd ../vault-infrastructure
   docker compose up -d
   ./scripts/init-vault.sh
   ```

2. **Store Keycloak Secrets in Vault**:
   ```bash
   cd ../keycloak-infrastructure
   ./scripts/init-keycloak.sh          # Generates random passwords
   ./scripts/store-secrets-in-vault.sh # Stores them in Vault
   ```

3. **Setup AppRole Authentication**:
   ```bash
   ./scripts/setup-vault-approle.sh
   ```
   
   This creates:
   - Vault policy for Keycloak
   - AppRole with appropriate permissions
   - Credentials file: `scripts/approle-credentials.txt`

4. **Setup Keycloak Role in Shared PKI**:
   ```bash
   ./scripts/setup-shared-pki-role.sh
   ```
   
   This creates:
   - PKI role `keycloak-server-localhost` in `pki_localhost` engine
   - Updates Keycloak policy to allow certificate generation
   - Uses same CA as Apache (unified certificate management)

5. **Update `.env` File**:
   
   The `.env` file should contain:
   ```bash
   # Vault AppRole Credentials
   VAULT_ROLE_ID=<role-id-from-approle-credentials.txt>
   VAULT_SECRET_ID=<secret-id-from-approle-credentials.txt>
   
   # Database Password (for PostgreSQL container only)
   KEYCLOAK_DB_PASSWORD=<db-password>
   ```

6. **Build and Start Keycloak**:
   ```bash
   docker compose build
   docker compose up -d
   ```

## Configuration Files

### `.env`

Contains only:
- Vault AppRole credentials (VAULT_ROLE_ID, VAULT_SECRET_ID)
- Database password (needed by PostgreSQL container, which doesn't support Vault)

### `docker-compose.yaml`

Key configurations:
```yaml
keycloak:
  build:
    context: .
    dockerfile: Dockerfile
  environment:
    # Vault connection
    VAULT_ADDR: https://shared_vault_server:8200
    VAULT_ROLE_ID: ${VAULT_ROLE_ID}
    VAULT_SECRET_ID: ${VAULT_SECRET_ID}
    
    # Database config (credentials fetched by entrypoint)
    KC_DB: postgres
    KC_DB_URL: jdbc:postgresql://keycloak_db:5432/keycloak
  networks:
    - keycloak_net
    - vault_net  # Connected to Vault network
```

### `policies/keycloak-policy.hcl`

Vault policy restricting Keycloak to read-only access:
```hcl
# Allow reading Keycloak database credentials
path "secret/data/keycloak/database" {
  capabilities = ["read"]
}

# Allow reading Keycloak admin credentials
path "secret/data/keycloak/admin" {
  capabilities = ["read"]
}

# Allow generating certificates from shared PKI (same as Apache)
path "pki_localhost/issue/keycloak-server-localhost" {
  capabilities = ["create", "update"]
}

# Allow reading CA certificate from shared PKI
path "pki_localhost/cert/ca" {
  capabilities = ["read"]
}
```

## Security Benefits

1. **No Plaintext Secrets**: Credentials never stored in files (except `.env` which contains only AppRole IDs)
2. **Centralized Management**: All secrets in one secure location
3. **Access Control**: Vault policies enforce least-privilege access
4. **Audit Trail**: Vault logs all secret access
5. **Rotation Support**: Secrets can be rotated without rebuilding containers
6. **Network Isolation**: Vault and Keycloak communicate over dedicated Docker network
7. **Unified PKI**: Same CA as Apache - clients only need to trust one certificate
8. **Automatic Certificate Renewal**: Certificates auto-renewed when expiring (< 7 days)

## Secret Rotation

To rotate secrets:

1. **Generate new password**:
   ```bash
   NEW_PASSWORD=$(openssl rand -base64 32)
   ```

2. **Update in Vault**:
   ```bash
   docker exec -e VAULT_TOKEN="$ROOT_TOKEN" -e VAULT_SKIP_VERIFY=1 shared_vault_server \
     vault kv put secret/keycloak/database \
       username="keycloak" \
       password="$NEW_PASSWORD"
   ```

3. **Update PostgreSQL**:
   ```bash
   docker exec shared_keycloak_db psql -U postgres -c \
     "ALTER USER keycloak WITH PASSWORD '$NEW_PASSWORD';"
   ```

4. **Restart Keycloak** (fetches new password):
   ```bash
   docker compose restart keycloak
   ```

## Troubleshooting

### Check Vault Connection

```bash
docker exec shared-keycloak-server vault status
```

### Verify Secrets

```bash
# From host with root token
export VAULT_TOKEN=$(jq -r '.root_token' ../vault-infrastructure/scripts/vault-keys.json)
docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 shared_vault_server \
  vault kv get secret/keycloak/database
```

### View Keycloak Logs

```bash
docker compose logs keycloak --tail=100
```

Successful startup shows:
```
=========================================
Keycloak Startup - Fetching Vault Secrets
=========================================
🔐 Authenticating with Vault...
✅ Authenticated with Vault
📥 Fetching database credentials...
📥 Fetching admin credentials...
✅ All credentials fetched successfully
=========================================
Starting Keycloak...
=========================================
```

### AppRole Issues

If authentication fails, regenerate the secret ID:

```bash
./scripts/setup-vault-approle.sh
# Update .env with new VAULT_SECRET_ID
docker compose restart keycloak
```

## Comparison: Before vs After Vault Integration

| Aspect | Before | After |
|--------|--------|-------|
| **Secret Storage** | `.env` file | Vault KV store |
| **Access Control** | File permissions | Vault policies + AppRole |
| **Audit** | None | Vault audit logs |
| **Rotation** | Manual env update + restart | Update Vault + restart |
| **Network** | Single network | Dedicated Vault network |
| **Security** | Plaintext in `.env` | Encrypted in Vault, fetched at runtime |
| **TLS Certificates** | Manual generation | Auto-generated from Vault PKI |
| **CA Trust** | Separate CA | Shared CA with Apache (pki_localhost) |

## Shared PKI with Apache

Both Keycloak and Apache use the same PKI engine (`pki_localhost`), which provides:

- **Single CA Certificate**: Clients only need to trust one CA
- **Consistent Certificate Management**: Same policies and procedures
- **Centralized Revocation**: CRL managed in one place
- **Simplified Trust Chain**: Reduced complexity for client configuration

To get the shared CA certificate:
```bash
docker exec shared_vault_server vault read -field=certificate pki_localhost/cert/ca > ca.crt
```

Import `ca.crt` into your browser or system trust store to trust both Apache and Keycloak.

## Related Documentation

- [README.md](README.md) - General Keycloak infrastructure documentation
- [QUICK_START.md](QUICK_START.md) - Quick setup guide
- [../vault-infrastructure/README.md](../vault-infrastructure/README.md) - Vault infrastructure documentation

## Notes

- The PostgreSQL container still uses `KEYCLOAK_DB_PASSWORD` from `.env` because it doesn't support Vault integration natively
- In production, consider using Vault's database secrets engine for dynamic credentials
- AppRole secret IDs should be rotated regularly (use `./scripts/setup-vault-approle.sh`)
- Keep `scripts/approle-credentials.txt` secure (permissions 600)
