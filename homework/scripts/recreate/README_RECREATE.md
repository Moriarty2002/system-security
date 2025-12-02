# Complete System Restoration Guide

This guide provides complete instructions to recreate the entire three-tier application system from scratch on a new machine.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Configuration Scripts](#configuration-scripts)
4. [Customization](#customization)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- Docker & Docker Compose
- Git
- `jq` (JSON processor)
- OpenSSL (for generating secrets)

### Repository Structure
Clone the repository and navigate to the homework directory:
```bash
git clone <repository-url>
cd homework
```

---

## Infrastructure Setup

### Step 1: Start Infrastructure Services

**1.1 Start Vault Infrastructure**
```bash
cd keycloak-infrastructure
docker compose up -d
```

Wait for Vault to be ready (~30 seconds).

**1.2 Initialize and Unseal Vault**
```bash
cd vault-infrastructure/scripts
./init-vault.sh
./unseal-vault.sh
```

This creates `vault-keys.json` with root token and unseal keys. **Save this file securely!**

Extract the root token:
```bash
export VAULT_TOKEN=$(jq -r '.root_token' vault-keys.json)
echo $VAULT_TOKEN  # Save this!
```

**1.3 Enable Vault Engines**
```bash
# Enable KV v2 secrets engine
docker exec shared_vault_server vault secrets enable -path=secret kv-v2

# Enable AppRole authentication
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server vault auth enable approle
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server vault auth enable -path=approle-apache approle
```

**1.4 Enable PKI Engine (for SSL certificates)**
```bash
cd ../../keycloak-infrastructure/scripts
./setup-shared-pki-role.sh
```

### Step 2: Start Keycloak Infrastructure

**2.1 Generate Keycloak Credentials**
```bash
cd ../keycloak-infrastructure
# Generate secure passwords
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

echo -n "admin" > secrets/admin_username.txt
echo -n "$ADMIN_PASSWORD" > secrets/admin_password.txt
echo -n "$DB_PASSWORD" > secrets/db_password.txt

chmod 600 secrets/*.txt
```

**2.2 Set up Vault AppRole for Keycloak**
```bash
cd scripts
./setup-vault-approle.sh
```

This creates `.env` file with `VAULT_ROLE_ID` and `VAULT_SECRET_ID`.

**2.3 Store Keycloak Secrets in Vault**
```bash
./store-secrets-in-vault.sh
```

**2.4 Start Keycloak**
```bash
cd ..
docker compose up -d
```

Wait for Keycloak to be healthy (~60 seconds):
```bash
docker logs shared-keycloak-server --follow
```

Look for: `Keycloak ... started`

### Step 3: Configure PKI and Issue Certificates

**3.1 Extract CA Private Key from Java Keystore**

If you have a CA in a Java keystore (`.pfx` or `.p12`):
```bash
cd ../4_three_tier_app/apache/certs

# Create Java extraction utility
javac ExtractCAPrivateKey.java

# Run extraction (adjust passwords as needed)
java ExtractCAPrivateKey key_store_CA.pfx keystore_psw "Unsecure psw"

# This creates: CA_private_key.pem, CA_cert_from_keystore.pem, CA_bundle.pem
```

**3.2 Import CA into Vault PKI Engine**
```bash
export VAULT_TOKEN=<your-vault-root-token>

# Import the CA bundle
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write pki_localhost/config/ca pem_bundle=@/path/to/CA_bundle.pem
```

**3.3 Create PKI Roles**
```bash
# Apache role
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write pki_localhost/roles/apache-server-localhost \
  allowed_domains="localhost,apache,apache-fe" \
  allow_bare_domains=true allow_localhost=true \
  max_ttl="720h" ttl="168h"

# Keycloak role
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write pki_localhost/roles/keycloak-server \
  allowed_domains="shared-keycloak-server,keycloak,localhost" \
  allow_bare_domains=true allow_localhost=true allow_subdomains=true \
  max_ttl="720h" ttl="168h"
```

**3.4 Issue Certificates**
```bash
# Issue Keycloak certificate
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write -format=json pki_localhost/issue/keycloak-server \
  common_name="shared-keycloak-server" \
  alt_names="keycloak,localhost" ttl="720h" > /tmp/keycloak_cert.json

# Extract and store in Vault
SERVER_CERT=$(jq -r '.data.certificate' /tmp/keycloak_cert.json)
SERVER_KEY=$(jq -r '.data.private_key' /tmp/keycloak_cert.json)
CA_CHAIN=$(jq -r '.data.ca_chain[0]' /tmp/keycloak_cert.json)

docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault kv put secret/keycloak/certificates \
  server_cert="$SERVER_CERT" \
  server_key="$SERVER_KEY" \
  ca_chain="$CA_CHAIN"

# Restart Keycloak to load certificates
cd ../../keycloak-infrastructure
docker compose restart keycloak
```

### Step 4: Configure Keycloak Realm and Users

**4.1 Set Environment Variables**
```bash
export KEYCLOAK_ADMIN_USER=admin
export KEYCLOAK_ADMIN_PASSWORD=$(cat secrets/admin_password.txt)
export VAULT_TOKEN=<your-vault-root-token>

# Optional customizations
export REALM_NAME=mes-local-cloud
export CLIENT_ID=mes-local-cloud-public
export CLIENT_ID_ADMIN=mes-local-cloud-admin-query
```

**4.2 Run Keycloak Setup Script**
```bash
cd ../scripts/recreate
chmod +x *.sh
./keycloak_setup.sh
```

This creates:
- Realm: `mes-local-cloud` (or custom name)
- Roles: `admin`, `moderator`, `user`
- Clients: `mes-local-cloud-public` (public), `mes-local-cloud-admin-query` (confidential)
- Users: `admin`, `alice`, `moderator` with passwords
- Role mappings and service account permissions

**4.3 Get mes-local-cloud-admin-query Client Secret**
```bash
ADMIN_CLIENT_ID=$(docker exec shared-keycloak-server \
  /opt/keycloak/bin/kcadm.sh get clients -r mes-local-cloud --fields id,clientId | \
  jq -r '.[] | select(.clientId=="mes-local-cloud-admin-query") | .id')

CLIENT_SECRET_ADMIN=$(docker exec shared-keycloak-server \
  /opt/keycloak/bin/kcadm.sh get clients/$ADMIN_CLIENT_ID/client-secret -r mes-local-cloud | \
  jq -r '.value')

echo "CLIENT_SECRET_ADMIN=$CLIENT_SECRET_ADMIN"
export CLIENT_SECRET_ADMIN
```

### Step 5: Configure Vault Secrets for Application

**5.1 Run Vault Setup Script**
```bash
./vault_setup.sh
```

**5.2 Store Application Secrets**
```bash
# Flask application secrets
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault kv put secret/mes_local_cloud/app/flask \
  jwt_secret=$(openssl rand -base64 32) \
  admin_password="admin" \
  alice_password="alice" \
  moderator_password="moderator"

# Database credentials
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault kv put secret/mes_local_cloud/database/postgres \
  username="admin" \
  password="devpass123_NeverUseInProduction" \
  database="postgres_db"

# MinIO credentials (generate secure keys)
MINIO_ACCESS_KEY="app-storage"
MINIO_SECRET_KEY=$(openssl rand -base64 32)

docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault kv put secret/mes_local_cloud/minio \
  access_key="$MINIO_ACCESS_KEY" \
  secret_key="$MINIO_SECRET_KEY" \
  endpoint="minio:9000" \
  bucket="user-files"
```

**5.3 Store CA Certificate for Flask Backend**
```bash
# Extract CA from Keycloak certificates
CA_CHAIN=$(docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault kv get -format=json secret/keycloak/certificates | jq -r '.data.data.ca_chain')

docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault kv patch secret/mes_local_cloud/app/flask \
  CA_chain="$CA_CHAIN"
```

### Step 6: Configure Application AppRoles

**6.1 Create AppRole for Flask Backend**
```bash
# Create policy
cat <<EOF > /tmp/flask-policy.hcl
path "secret/data/mes_local_cloud/*" {
  capabilities = ["read"]
}
path "secret/data/keycloak/client" {
  capabilities = ["read"]
}
EOF

docker cp /tmp/flask-policy.hcl shared_vault_server:/tmp/
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault policy write flask-policy /tmp/flask-policy.hcl

# Create AppRole
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write auth/approle/role/mes-local-cloud-public \
  token_policies="flask-policy" \
  token_ttl=1h token_max_ttl=4h

# Get credentials
FLASK_ROLE_ID=$(docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault read -field=role_id auth/approle/role/mes-local-cloud-public/role-id)

FLASK_SECRET_ID=$(docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write -field=secret_id -f auth/approle/role/mes-local-cloud-public/secret-id)

echo "FLASK_ROLE_ID=$FLASK_ROLE_ID"
echo "FLASK_SECRET_ID=$FLASK_SECRET_ID"
```

**6.2 Create AppRole for Apache**
```bash
# Create policy
cat <<EOF > /tmp/apache-policy.hcl
path "secret/data/mes_local_cloud/certificates/apache" {
  capabilities = ["read"]
}
path "pki_localhost/issue/apache-server-localhost" {
  capabilities = ["create", "update"]
}
EOF

docker cp /tmp/apache-policy.hcl shared_vault_server:/tmp/
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault policy write apache-policy /tmp/apache-policy.hcl

# Create AppRole
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write auth/approle-apache/role/apache-frontend \
  token_policies="apache-policy" \
  token_ttl=1h token_max_ttl=4h

# Get credentials
APACHE_ROLE_ID=$(docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault read -field=role_id auth/approle-apache/role/apache-frontend/role-id)

APACHE_SECRET_ID=$(docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write -field=secret_id -f auth/approle-apache/role/apache-frontend/secret-id)

echo "APACHE_ROLE_ID=$APACHE_ROLE_ID"
echo "APACHE_SECRET_ID=$APACHE_SECRET_ID"
```

**6.3 Issue Apache Certificates**
```bash
# Issue certificate from PKI
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault write -format=json pki_localhost/issue/apache-server-localhost \
  common_name="localhost" alt_names="apache,apache-fe" ttl="720h" > /tmp/apache_cert.json

# Extract and store
APACHE_CERT=$(jq -r '.data.certificate' /tmp/apache_cert.json)
APACHE_KEY=$(jq -r '.data.private_key' /tmp/apache_cert.json)
APACHE_CA=$(jq -r '.data.ca_chain[0]' /tmp/apache_cert.json)

docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault kv put secret/mes_local_cloud/certificates/apache \
  server_cert="$APACHE_CERT" \
  server_key="$APACHE_KEY" \
  ca_chain="$APACHE_CA"
```

### Step 7: Start Application Stack

**7.1 Configure Application .env File**
```bash
cd ../../../4_three_tier_app

cat > .env <<EOF
# Vault Configuration
VAULT_ADDR=https://shared_vault_server:8200
VAULT_SKIP_VERIFY=false
VAULT_ROLE_ID=$FLASK_ROLE_ID
VAULT_SECRET_ID=$FLASK_SECRET_ID

# Apache Vault Configuration
APACHE_VAULT_ADDR=https://shared_vault_server:8200
APACHE_VAULT_SKIP_VERIFY=false
APACHE_VAULT_ROLE_ID=$APACHE_ROLE_ID
APACHE_VAULT_SECRET_ID=$APACHE_SECRET_ID

# Keycloak Configuration
KEYCLOAK_SERVER_URL=https://shared-keycloak-server:8443
KEYCLOAK_REALM=mes-local-cloud
KEYCLOAK_CLIENT_ID=mes-local-cloud-public
EOF
```

**7.2 Start Application Services**
```bash
docker compose up -d
```

Wait for services to be healthy (~30 seconds):
```bash
docker compose ps
```

### Step 8: Initialize MinIO

**8.1 Create MinIO User and Bucket**
```bash
cd minio/scripts
./create_minio_user.sh
```

This creates:
- Bucket: `user-files`
- User: `app-storage` with appropriate permissions

### Step 9: Initialize Database

**9.1 Run Database Setup Script**
```bash
cd ../../scripts/recreate
./db_setup.sh
```

This creates `user_profiles` entries for all Keycloak users.

---

## Configuration Scripts

The following scripts are provided for automation:

### keycloak_setup.sh
Creates realm, roles, clients, users, and role mappings.

**Environment Variables:**
- `KEYCLOAK_ADMIN_USER` (default: admin)
- `KEYCLOAK_ADMIN_PASSWORD` (required)
- `REALM_NAME` (default: mes-local-cloud)
- `KC_CONTAINER` (default: shared-keycloak-server)

### vault_setup.sh
Writes Keycloak client configuration to Vault.

**Environment Variables:**
- `VAULT_TOKEN` (required)
- `CLIENT_ID` (default: mes-local-cloud-public)
- `CLIENT_SECRET` (required)
- `CLIENT_ID_ADMIN` (default: mes-local-cloud-admin-query)
- `CLIENT_SECRET_ADMIN` (required)
- `REALM` (default: mes-local-cloud)
- `SERVER_URL` (default: https://shared-keycloak-server:8443)
- `VAULT_CONTAINER` (default: shared_vault_server)

### db_setup.sh
Fetches Keycloak users and creates database profiles.

**Environment Variables:**
- `KC_CONTAINER` (default: shared-keycloak-server)
- `PG_CONTAINER` (default: postgres_db)
- `REALM` (default: mes-local-cloud)
- `PG_USER` (default: admin)
- `PG_DB` (default: postgres_db)

### restore_all.sh
Orchestrator that runs all scripts in order.

---

## Customization

### Changing Realm Name

To use a different realm name:

1. Export the variable before running scripts:
```bash
export REALM_NAME=my-custom-realm
```

2. Update application configuration:
```bash
# In 4_three_tier_app/.env
KEYCLOAK_REALM=my-custom-realm
```

3. Update Vault secrets:
```bash
docker exec -e VAULT_TOKEN=$VAULT_TOKEN shared_vault_server \
  vault kv patch secret/keycloak/client realm=my-custom-realm
```

### Changing Container Names

Edit the following variables at the top of each script:
- `KC_CONTAINER` - Keycloak container name
- `VAULT_CONTAINER` - Vault container name
- `PG_CONTAINER` - PostgreSQL container name

Or export them before running:
```bash
export KC_CONTAINER=my-keycloak
export VAULT_CONTAINER=my-vault
export PG_CONTAINER=my-postgres
```

### Adding Custom Users

Edit `keycloak_setup.sh` and add:
```bash
docker exec ${KC_CONTAINER} ${KCADM} create users -r ${REALM_NAME} \
  -s username=newuser -s enabled=true
docker exec ${KC_CONTAINER} ${KCADM} set-password -r ${REALM_NAME} \
  --username newuser --new-password password123
docker exec ${KC_CONTAINER} ${KCADM} add-roles -r ${REALM_NAME} \
  --uusername newuser --rolename user
```

Then run `db_setup.sh` to create their profile.

---

## Verification

### Check All Services Are Running
```bash
# Check Vault
docker exec shared_vault_server vault status

# Check Keycloak
curl -k https://localhost:8443/realms/mes-local-cloud

# Check Application
curl -k https://localhost

# Check all containers
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

### Test Authentication
```bash
# Get token for alice
TOKEN=$(curl -k -s -X POST "https://localhost:8443/realms/mes-local-cloud/protocol/openid-connect/token" \
  -d "grant_type=password" \
  -d "client_id=mes-local-cloud-public" \
  -d "username=alice" \
  -d "password=alice" | jq -r '.access_token')

# Test backend API
curl -k -s -H "Authorization: Bearer $TOKEN" https://localhost/api/auth/whoami | jq
```

Expected output:
```json
{
  "keycloak_id": "<uuid>",
  "role": "user",
  "username": "alice"
}
```

### Test File Upload
```bash
echo "test content" > /tmp/test.txt
curl -k -s -X POST https://localhost/api/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test.txt" | jq
```

Expected output:
```json
{
  "filename": "test.txt",
  "size": 13,
  "status": "ok"
}
```

---

## Troubleshooting

### Vault Sealed
If Vault shows "sealed=true":
```bash
cd vault-infrastructure/scripts
./unseal-vault.sh
```

### Keycloak Not Starting
Check logs:
```bash
docker logs shared-keycloak-server --tail 50
```

Common issues:
- Database connection failed: Check `KEYCLOAK_DB_PASSWORD` in Vault
- Certificate errors: Verify certificates are stored in Vault

### Application Can't Connect to Keycloak

Check SSL certificate:
```bash
# Verify CA is installed in Flask container
docker exec flask_be ls -la /usr/local/share/ca-certificates/

# Reinstall if missing
docker exec flask_be /usr/local/bin/install_ca.sh
```

### Database Connection Errors

Verify credentials:
```bash
docker exec postgres_db psql -U admin -d postgres_db -c "\dt"
```

### MinIO Access Denied

Recreate MinIO user:
```bash
cd 4_three_tier_app/minio/scripts
./create_minio_user.sh
```

---

## Security Notes

- These scripts use development passwords and are NOT production-ready
- Always use strong, randomly generated passwords in production
- Enable Vault audit logging: `docker exec shared_vault_server vault audit enable file file_path=/vault/logs/audit.log`
- Use TLS for all inter-service communication
- Regularly rotate secrets and certificates
- Never commit `vault-keys.json` or `.env` files to version control

---

## Quick Reference

**Default Credentials:**
- Keycloak Master Admin: `admin` / (from `secrets/admin_password.txt`)
- Realm Users:
  - `admin` / `admin` (role: admin)
  - `alice` / `alice` (role: user)
  - `moderator` / `moderator` (role: moderator)

**URLs:**
- Application: https://localhost
- Keycloak Admin: https://localhost:8443
- Keycloak Realm: https://localhost:8443/realms/mes-local-cloud
- Vault: https://localhost:8200
- MinIO Console: http://localhost:9001

**Container Names:**
- `shared_vault_server`
- `shared-keycloak-server`
- `shared_keycloak_db`
- `postgres_db`
- `minio_storage`
- `flask_be`
- `apache_fe`
