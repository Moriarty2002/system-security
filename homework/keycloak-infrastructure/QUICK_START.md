# Keycloak Infrastructure - Quick Start Guide

## Overview

✅ **Vault-Integrated Keycloak** - All secrets from Vault  
✅ **httpsS Support** - TLS certificates from Vault PKI (shared with Apache)  
✅ **Separate Infrastructure** - Independent lifecycle from applications  
✅ **Centralized SSO** - OpenID Connect authentication for all apps  
✅ **Automatic Certificate Management** - Fetched from Vault at startup  

## Prerequisites

1. **Vault Infrastructure Running**:
   ```bash
   cd vault-infrastructure
   docker compose ps  # Verify shared_vault_server is running
   ```

2. **Vault Initialized and Unsealed**:
   ```bash
   cd vault-infrastructure/scripts
   ./init-vault.sh  # If not already done
   ```

## Setup Steps

### Step 1: Store Keycloak Secrets in Vault

```bash
cd keycloak-infrastructure/scripts

# Generate random passwords and store in Vault
./init-keycloak.sh
./store-secrets-in-vault.sh

# Setup AppRole authentication for Keycloak
./setup-vault-approle.sh
```

**Credentials saved to Vault:**
- `secret/keycloak/database` - Database username/password
- `secret/keycloak/admin` - Admin username/password

### Step 2: Configure TLS Certificates (Optional)

**Option A: Add Certificate via Vault UI** (Recommended)
1. Access Vault UI: httpss://localhost:8200
2. Login with root token (from `vault-infrastructure/scripts/vault-keys.json`)
3. Navigate to: **Secrets** > **secret** > **Create secret**
4. Path: `keycloak/certificates`
5. Add secret data:
   ```
   server_cert: <paste certificate>
   server_key: <paste private key>
   ca_chain: <paste CA certificate>
   ```

**Option B: Use Script** (For testing)
```bash
# Uses existing Apache PKI to generate certificate
./scripts/setup-shared-pki-role.sh
```

**Note:** Keycloak runs on https (port 8443) if no certificate provided, httpsS (port 8443) when certificate exists.

### Step 3: Update Environment Variables

```bash
cd keycloak-infrastructure
cat scripts/approle-credentials.txt  # Copy VAULT_ROLE_ID and VAULT_SECRET_ID

# Update .env file
vim .env
```

Ensure `.env` contains:
```bash
# Vault AppRole Credentials
VAULT_ROLE_ID=<your-role-id>
VAULT_SECRET_ID=<your-secret-id>

# Database Password (for PostgreSQL container)
KEYCLOAK_DB_PASSWORD=<your-db-password>
```

### Step 4: Start Keycloak Infrastructure

```bash
docker compose build
docker compose up -d
```

**Verify startup:**
```bash
docker compose ps
# Both containers should show "healthy"

docker compose logs keycloak | grep "credentials fetched"
# Should see: ✅ All credentials fetched successfully
```

**Access Points:**
- **https**: https://localhost:8443 (always available)
- **httpsS**: httpss://localhost:8443 (if certificate added to Vault)

### Step 5: Login to Keycloak Admin Console

1. Open: https://localhost:8443 or httpss://localhost:8443
2. Click: **Administration Console**
3. Login:
   - Username: `admin` (default)
   - Password: Get from Vault or `secrets/admin_password.txt`

**Get admin password:**
```bash
# From Vault
cd keycloak-infrastructure
docker exec shared_vault_server vault kv get -field=password secret/keycloak/admin

# Or from generated file
cat secrets/admin_password.txt
```

## Keycloak Configuration (Detailed)

### Step 6: Create Realm

1. Hover over **Master** (top-left)
2. Click **Create Realm**
3. Configure:
   - **Realm name**: `mes-local-cloud`
   - **Enabled**: ON
4. Click **Create**

### Step 7: Configure Realm Settings (Security)

Navigate to: **Realm Settings** > **Security defenses**

**Configure Brute Force Detection:**
- **Enabled**: ON
- **Max login failures**: 5
- **Wait increment**: 60 seconds
- **Quick login check**: 1000ms
- **Minimum quick login wait**: 60 seconds
- **Max wait**: 15 minutes
- **Failure reset time**: 12 hours

**Configure Headers:**
- Navigate to: **Realm Settings** > **Security defenses** > **Headers**
- **X-Frame-Options**: SAMEORIGIN
- **Content-Security-Policy**: frame-src 'self'; frame-ancestors 'self'; object-src 'none';
- **X-Content-Type-Options**: nosniff
- **X-XSS-Protection**: 1; mode=block
- **Strict-Transport-Security**: max-age=31536000; includeSubDomains

**Configure Sessions:**
- Navigate to: **Realm Settings** > **Sessions**
- **SSO Session Idle**: 30 minutes
- **SSO Session Max**: 10 hours
- **Access Token Lifespan**: 5 minutes
- **Refresh Token Lifespan**: 30 minutes

### Step 8: Create Client (OpenID Connect)

Navigate to: **Clients** > **Create client**

**Step 1 - General Settings:**
- **Client type**: OpenID Connect
- **Client ID**: `mes-local-cloud-api`
- Click **Next**

**Step 2 - Capability config:**
- **Client authentication**: ON (confidential client)
- **Authorization**: OFF (not needed for this use case)
- **Authentication flow**:
  - ✅ Standard flow
  - ✅ Direct access grants
  - ❌ Implicit flow (insecure, disable)
  - ❌ Service accounts roles
  - ❌ OAuth 2.0 Device Authorization Grant
- Click **Next**

**Step 3 - Login settings:**
- **Root URL**: `https://localhost` (or your domain)
- **Home URL**: `https://localhost`
- **Valid redirect URIs**: 
  - `https://localhost/*`
  - `https://localhost:80/*`
  - (Add httpsS when certificate configured)
- **Valid post logout redirect URIs**: `https://localhost/*`
- **Web origins**: 
  - `https://localhost`
  - `+` (allows all redirect URIs)
- Click **Save**

**Step 4 - Advanced Settings (Security):**

Navigate to: **Clients** > `mes-local-cloud-api` > **Advanced** tab

- **Access Token Lifespan**: 5 minutes
- **Client Session Idle**: 30 minutes
- **Client Session Max**: 10 hours
- **OAuth 2.0 Mutual TLS Certificate Bound Access Tokens**: OFF (unless using mTLS)
- **PKCE Code Challenge Method**: S256 (recommended for SPAs)

**Step 5 - Get Client Secret:**

Navigate to: **Clients** > `mes-local-cloud-api` > **Credentials** tab
- Copy **Client secret** (you'll need this for backend configuration)

### Step 9: Create Roles

Navigate to: **Realm roles** > **Create role**

Create three roles with the following configurations:

**1. Admin Role:**
- **Role name**: `admin`
- **Description**: `Administrator with full access`
- Click **Save**

**2. Moderator Role:**
- **Role name**: `moderator`
- **Description**: `Moderator with elevated privileges`
- Click **Save**

**3. User Role:**
- **Role name**: `user`
- **Description**: `Standard user with basic access`
- Click **Save**


### Step 10: Create Users

Navigate to: **Users** > **Add user**

**Example User - Admin:**
1. **Username**: `admin`
2. **Email**: `admin@localhost`
3. **Email verified**: ON
4. **First name**: `Admin`
5. **Last name**: `User`
6. **Enabled**: ON
7. Click **Create**

**Set Password:**
1. Go to **Credentials** tab
2. Click **Set password**
3. Enter password
4. **Temporary**: OFF (user won't need to change it)
5. Click **Save**

**Assign Roles:**
1. Go to **Role mapping** tab
2. Click **Assign role**
3. Filter: **Filter by clients** or **Filter by realm roles**
4. Select `admin` role
5. Click **Assign**

**Repeat for other users** (moderator, alice, etc.):
- Moderator: Assign `moderator` role
- Regular users: Assign `user` role

### Step 11: Configure Role Mapping in Tokens

Navigate to: **Clients** > `mes-local-cloud-api` > **Client scopes** > `mes-local-cloud-api-dedicated`

**Add Realm Roles to Token:**
1. Click **Add mapper** > **By configuration**
2. Select **User Realm Role**
3. Configure:
   - **Name**: `realm-roles`
   - **Token Claim Name**: `roles`
   - **Claim JSON Type**: String
   - **Add to ID token**: ON
   - **Add to access token**: ON
   - **Add to userinfo**: ON
4. Click **Save**

**Add Username to Token:**
1. Click **Add mapper** > **By configuration**
2. Select **User Property**
3. Configure:
   - **Name**: `username`
   - **Property**: `username`
   - **Token Claim Name**: `preferred_username`
   - **Claim JSON Type**: String
   - **Add to ID token**: ON
   - **Add to access token**: ON
   - **Add to userinfo**: ON
4. Click **Save**

### Step 12: Test OpenID Connect Configuration

**Get OpenID Configuration:**
```bash
curl https://localhost:8443/realms/mes-local-cloud/.well-known/openid-configuration | jq
```

**Verify endpoints:**
- `authorization_endpoint`
- `token_endpoint`
- `userinfo_endpoint`
- `jwks_uri`

**Test Token Generation (Direct Access Grant):**
```bash
# Get access token
curl -X POST "https://localhost:8443/realms/mes-local-cloud/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=mes-local-cloud-api" \
  -d "client_secret=<your-client-secret>" \
  -d "username=admin" \
  -d "password=<admin-password>" | jq

# Decode token to verify roles
# Copy access_token from above response
echo "<access-token>" | cut -d'.' -f2 | base64 -d | jq
```

**Verify token contains:**
- `preferred_username`: "admin"
- `roles`: ["admin", "moderator", "user"] (if using composite roles)

## Application Integration

### Step 13: Store Keycloak Client Credentials in Vault

**Instead of using `.env` files, store Keycloak client configuration securely in Vault:**

```bash
# Store client credentials in Vault (from shared Vault server)
docker exec shared_vault_server vault kv put secret/keycloak/client \
  server_url="https://shared-keycloak-server:8443" \
  realm="mes-local-cloud" \
  client_id="mes-local-cloud-api" \
  client_secret="<your-client-secret-from-step-8>"
```

**Verify stored credentials:**
```bash
docker exec shared_vault_server vault kv get secret/keycloak/client
```

**Update application's Vault policy** (if not already done):

```bash
cd 4_three_tier_app

# Ensure AppRole policy includes Keycloak secrets
docker exec shared_vault_server vault policy write mes_local_cloud - << EOF
# Application secrets
path "secret/data/mes_local_cloud/*" {
  capabilities = ["read"]
}

# Keycloak client configuration
path "secret/data/keycloak/client" {
  capabilities = ["read"]
}

# MinIO credentials
path "secret/data/minio/app" {
  capabilities = ["read"]
}

# Database credentials
path "secret/data/database/app" {
  capabilities = ["read"]
}
EOF
```

**Note:** Your backend already supports Vault integration via `vault_client.get_keycloak_config()` which reads from `secret/keycloak/client`.

**Verify docker-compose.yaml network connection** (should already exist):
```yaml
services:
  backend:
    networks:
      - app_net
      - shared_keycloak_network  # Connect to Keycloak network
      - shared_vault_net          # Connect to Vault network

networks:
  shared_keycloak_network:
    external: true
  shared_vault_net:
    external: true
```

### Step 14: Start Application

```bash
cd 4_three_tier_app
docker compose up -d
```

**Verify connection:**
```bash
docker compose logs backend | grep -i keycloak
# Should see successful JWKS fetch
```

### Step 15: Test Authentication Flow

1. Open: https://localhost
2. Try to access protected resource
3. Should redirect to Keycloak login
4. Login with created user
5. Should redirect back with access token
6. Verify role-based access control

## Security Checklist

✅ **Secrets Management:**
- All credentials stored in Vault
- No plaintext passwords in config files
- AppRole authentication for service-to-service

✅ **TLS/httpsS:**
- Certificates from Vault PKI
- Shared CA with Apache (unified trust)
- Automatic certificate retrieval at startup

✅ **Keycloak Security:**
- Brute force protection enabled
- Security headers configured
- Short token lifespans (5 min access, 30 min refresh)
- Session timeouts configured
- Implicit flow disabled
- PKCE enabled for SPAs

✅ **OpenID Connect:**
- Confidential client (client secret required)
- Proper redirect URI validation
- Role claims in tokens
- Standard flow for web apps
- Direct access grants for APIs

✅ **Network Isolation:**
- Separate Docker networks
- Keycloak not directly exposed to internet
- Backend-to-Keycloak communication isolated

## Maintenance Commands

## Maintenance Commands

### View Keycloak Status

```bash
cd keycloak-infrastructure
docker compose ps
docker compose logs keycloak --tail=50
```

### Restart Keycloak

```bash
docker compose restart keycloak
```

### Update Secrets in Vault

```bash
# Update admin password
docker exec shared_vault_server vault kv put secret/keycloak/admin \
  username="admin" \
  password="new-secure-password"

# Restart to fetch new secrets
docker compose restart keycloak
```

### Add/Update TLS Certificate

```bash
# Via Vault UI: Update secret/keycloak/certificates
# Then restart:
docker compose restart keycloak
```

### Backup Database

```bash
./scripts/backup.sh
```

### View Vault Credentials

```bash
# Database password
docker exec shared_vault_server vault kv get secret/keycloak/database

# Admin password
docker exec shared_vault_server vault kv get secret/keycloak/admin
```

### Rotate AppRole Secret

```bash
./scripts/setup-vault-approle.sh
# Update .env with new VAULT_SECRET_ID
docker compose restart keycloak
```

## Troubleshooting

### Keycloak Can't Connect to Vault

```bash
# Verify Vault is running
docker ps | grep shared_vault_server

# Check network connectivity
docker exec shared-keycloak-server ping shared_vault_server

# Verify Vault token
docker exec shared-keycloak-server vault status
```

### Certificate Not Loading (httpsS)

```bash
# Check certificate exists in Vault
docker exec shared_vault_server vault kv get secret/keycloak/certificates

# Verify certificate files in container
docker exec shared-keycloak-server ls -l /opt/keycloak/certs/

# Check logs for certificate fetch
docker compose logs keycloak | grep certificate
```

### Backend Can't Connect to Keycloak

```bash
# Verify Keycloak is running
docker ps | grep shared-keycloak-server

# Test from backend container
docker exec flask_be curl https://shared-keycloak-server:8443/realms/mes-local-cloud

# Check network membership
docker network inspect shared_keycloak_network | grep flask_be
```

### Forgot Admin Password

```bash
# Get from Vault
docker exec shared_vault_server vault kv get -field=password secret/keycloak/admin

# Or from generated file
cat secrets/admin_password.txt
```

### Reset Everything

```bash
# WARNING: Deletes all data!
docker compose down -v
rm -rf secrets/
./scripts/init-keycloak.sh
./scripts/store-secrets-in-vault.sh
./scripts/setup-vault-approle.sh
# Update .env with new credentials
docker compose up -d
# Reconfigure realm, client, users
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Vault Infrastructure (shared_vault_net)    │
│  ┌──────────────┐                          │
│  │ Vault Server │ ← Stores secrets & certs  │
│  └──────┬───────┘                          │
└─────────┼──────────────────────────────────┘
          │
          │ Fetches secrets & certificates
          │
┌─────────▼──────────────────────────────────┐
│  Keycloak Infrastructure                    │
│  (shared_keycloak_network + shared_vault_net)│
│                                             │
│  ┌────────────────┐                        │
│  │ Keycloak       │ :8443 (https)           │
│  │                │ :8443 (httpsS)          │
│  └───────┬────────┘                        │
│          │                                  │
│  ┌───────▼────────┐                        │
│  │ PostgreSQL DB  │                        │
│  └────────────────┘                        │
└─────────┬──────────────────────────────────┘
          │
          │ OpenID Connect / OAuth2
          │
┌─────────▼──────────────────────────────────┐
│  Application (4_three_tier_app)             │
│  (app_net + shared_keycloak_network)        │
│                                             │
│  ┌────────────┐  ┌────────────┐           │
│  │ Backend    │  │ PostgreSQL │           │
│  │ (Flask)    │  │            │           │
│  └─────┬──────┘  └────────────┘           │
│        │                                    │
│  ┌─────▼──────┐  ┌────────────┐           │
│  │ Apache     │  │ MinIO      │           │
│  │ :80, :443  │  │            │           │
│  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────┘
```

## Token Flow (OpenID Connect)

1. **User accesses application** → Frontend redirects to Keycloak
2. **User authenticates** → Keycloak validates credentials
3. **Keycloak issues tokens** → Access token + ID token + Refresh token
4. **Frontend receives tokens** → Stores in secure cookie/storage
5. **API requests** → Backend validates access token signature (RS256)
6. **Backend extracts roles** → From token claims (`roles` array)
7. **Authorization check** → Role-based access control
8. **Token refresh** → When access token expires (5 min)

## Security Best Practices Applied

✅ **Confidential Client** - Client secret required (not public)  
✅ **Short-lived Access Tokens** - 5 minutes prevents token theft impact  
✅ **Refresh Token Rotation** - New refresh token issued on use  
✅ **PKCE Enabled** - Protection against authorization code interception  
✅ **Brute Force Protection** - Account lockout after failed attempts  
✅ **Security Headers** - XSS, CSRF, Clickjacking protection  
✅ **httpsS Support** - TLS for production deployments  
✅ **Role-based Claims** - Fine-grained authorization  
✅ **Network Isolation** - Keycloak not directly exposed  
✅ **Vault Integration** - Centralized secret management  

## Production Considerations

Before deploying to production:

1. **Enable httpsS Only:**
   - Add TLS certificate to Vault
   - Set `KC_https_ENABLED=false`
   - Update `KC_HOSTNAME_STRICT=true`

2. **Use Production Mode:**
   - Change `start-dev` to `start` in docker-compose.yaml
   - Configure proper hostname
   - Set up reverse proxy (nginx/traefik)

3. **Database Backups:**
   - Schedule regular backups
   - Test restore procedures
   - Store backups securely

4. **Monitoring:**
   - Enable Keycloak metrics
   - Set up health check monitoring
   - Configure alerting

5. **High Availability:**
   - Deploy multiple Keycloak instances
   - Use load balancer
   - Configure database replication

6. **Security Hardening:**
   - Rotate secrets regularly
   - Enable audit logging
   - Review security policies
   - Keep Keycloak updated

## Related Documentation

- **README.md** - Complete infrastructure documentation
- **VAULT_INTEGRATION.md** - Vault integration details
- **httpsS_SETUP.md** - TLS certificate configuration
- **../4_three_tier_app/KEYCLOAK_MIGRATION.md** - Application migration guide

---

**Quick Reference Card:**

| Task | Command |
|------|---------|
| Start | `docker compose up -d` |
| Stop | `docker compose down` |
| Logs | `docker compose logs -f keycloak` |
| Status | `docker compose ps` |
| Admin Console | https://localhost:8443 |
| Admin Password | `cat secrets/admin_password.txt` |
| Backup | `./scripts/backup.sh` |
| Vault Secrets | `docker exec shared_vault_server vault kv get secret/keycloak/admin` |
