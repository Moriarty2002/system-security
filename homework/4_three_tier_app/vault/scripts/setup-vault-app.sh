#!/bin/bash
# Application-Specific Vault Configuration
# 
# This script configures the shared Vault server for the 4_three_tier_app application.
# It creates policies, AppRoles, and stores application secrets.
#
# Prerequisites:
#   - Shared Vault must be running: cd ../../vault-infrastructure && docker compose up -d
#   - Shared Vault must be initialized: cd ../../vault-infrastructure/scripts && ./init-vault.sh
#   - Shared Vault must be unsealed
#
# Usage: ./setup-vault-app.sh

set -e

VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."
SHARED_VAULT_KEYS="$SCRIPT_DIR/../../../vault-infrastructure/scripts/vault-keys.json"
VAULT_CONTAINER="shared_vault_server"
APP_CREDENTIALS_FILE="$SCRIPT_DIR/approle-credentials.txt"

# Helper function to run vault commands in container
vault_exec() {
    if [ -n "$VAULT_TOKEN" ]; then
        docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
    else
        docker exec -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
    fi
}

echo "==================================="
echo "4_three_tier_app Vault Configuration"
echo "==================================="
echo ""
echo "Vault Address: $VAULT_ADDR"
echo ""

# Check if Vault container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${VAULT_CONTAINER}$"; then
    echo "❌ Error: Shared Vault container is not running"
    echo "Please start Vault: cd ../../vault-infrastructure && docker compose up -d"
    exit 1
fi

# Check if Vault is accessible
if ! curl -sk "$VAULT_ADDR/v1/sys/health" > /dev/null 2>&1; then
    echo "❌ Error: Vault is not accessible at $VAULT_ADDR"
    exit 1
fi

# Check if shared vault-keys.json exists
if [ ! -f "$SHARED_VAULT_KEYS" ]; then
    echo "❌ Error: Shared vault-keys.json not found at $SHARED_VAULT_KEYS"
    echo "Please initialize shared Vault: cd ../../vault-infrastructure/scripts && ./init-vault.sh"
    exit 1
fi

# Get root token from shared Vault
ROOT_TOKEN=$(jq -r '.root_token' "$SHARED_VAULT_KEYS")
VAULT_TOKEN="$ROOT_TOKEN"

# Check if Vault is unsealed
if vault_exec status 2>&1 | grep -q "Sealed.*true"; then
    echo "❌ Error: Vault is sealed"
    echo "Please unseal Vault: cd ../../vault-infrastructure/scripts && ./unseal-vault.sh"
    exit 1
fi

echo "✅ Connected to shared Vault"
echo ""

# Write application policies
echo "==================================="
echo "Creating Application Policies..."
echo "==================================="
echo ""

echo "Creating app-policy for 4_three_tier_app..."
docker exec -i -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault policy write mes_local_cloud-app - < "$SCRIPT_DIR/../policies/app-policy.hcl"
echo "✅ Application policy created"

echo ""
echo "Creating admin-policy for 4_three_tier_app..."
docker exec -i -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault policy write mes_local_cloud-admin - < "$SCRIPT_DIR/../policies/admin-policy.hcl"
echo "✅ Admin policy created"

echo ""
echo "Creating PKI policy for Apache..."
docker exec -i -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault policy write pki-policy - < "$SCRIPT_DIR/../policies/pki-policy.hcl"
echo "✅ PKI policy created"

# Create AppRole for Flask application
echo ""
echo "==================================="
echo "Creating AppRoles..."
echo "==================================="
echo ""

echo "Creating AppRole for Flask backend..."
vault_exec write auth/approle/role/mes_local_cloud-flask-app \
    token_policies="mes_local_cloud-app" \
    token_ttl=1h \
    token_max_ttl=4h \
    bind_secret_id=true \
    secret_id_ttl=0

echo "✅ AppRole 'mes_local_cloud-flask-app' created"

# Get Role ID and Secret ID for Flask backend
ROLE_ID=$(vault_exec read -field=role_id auth/approle/role/mes_local_cloud-flask-app/role-id)
SECRET_ID=$(vault_exec write -field=secret_id -f auth/approle/role/mes_local_cloud-flask-app/secret-id)

echo ""
echo "Creating AppRole for Apache frontend..."
vault_exec write auth/approle-apache/role/apache-server \
    token_policies="pki-policy" \
    token_ttl=1h \
    token_max_ttl=4h \
    bind_secret_id=true \
    secret_id_ttl=0 2>/dev/null || echo "Note: Apache AppRole may need PKI policy setup first"

# Get Role ID and Secret ID for Apache
APACHE_ROLE_ID=$(vault_exec read -field=role_id auth/approle-apache/role/apache-server/role-id 2>/dev/null || echo "not-configured")
APACHE_SECRET_ID=$(vault_exec write -field=secret_id -f auth/approle-apache/role/apache-server/secret-id 2>/dev/null || echo "not-configured")

# Save AppRole credentials
cat > "$APP_CREDENTIALS_FILE" <<EOF
4_three_tier_app Flask Application AppRole Credentials
===================================================
Role ID: $ROLE_ID
Secret ID: $SECRET_ID

⚠️  IMPORTANT: Store these credentials securely!
⚠️  The Secret ID is only shown once and should be provided to the Flask application.
⚠️  Add these to your .env file or environment variables.

To rotate Secret ID: ./rotate-secret-id.sh
EOF

echo "✅ AppRole credentials saved to: $APP_CREDENTIALS_FILE"

# Generate secure secrets
echo ""
echo "==================================="
echo "Generating and Storing Secrets..."
echo "==================================="
echo ""

# Generate a secure JWT secret key
JWT_SECRET=$(openssl rand -base64 32)
echo "Generated JWT secret key..."

# Generate secure passwords for database users
DB_ADMIN_PASSWORD="devpass123_NeverUseInProduction"
DB_APP_PASSWORD="flask_app_secure_password"  # Existing password - matches current DB
echo "Using database passwords..."

# Store application secrets in namespaced path
vault_exec kv put secret/mes_local_cloud/app/flask \
    jwt_secret="$JWT_SECRET" \
    admin_password="admin" \
    alice_password="alice" \
    moderator_password="moderator"

echo "✅ Application secrets stored at secret/mes_local_cloud/app/flask"

# Store database secrets in namespaced path (used by Flask application - least privilege)
vault_exec kv put secret/mes_local_cloud/database/postgres \
    username="flask_app" \
    password="$DB_APP_PASSWORD" \
    database="postgres_db" \
    host="db" \
    port="5432"

echo "✅ Database secrets stored at secret/mes_local_cloud/database/postgres"
echo "   Note: Flask connects as 'flask_app' user with limited privileges"
echo "   ⚠️  IMPORTANT: If updating existing Vault, manually run:"
echo "      vault kv put secret/mes_local_cloud/database/postgres username=flask_app password=flask_app_secure_password database=postgres_db host=db port=5432"

# Generate and store MinIO application user credentials
echo ""
echo "Generating MinIO application user credentials..."

# Generate secure credentials for MinIO application user
MINIO_APP_USER="app-storage"
MINIO_APP_PASSWORD=$(openssl rand -base64 32)

# Store MinIO credentials in Vault (using dedicated app user, not root)
vault_exec kv put secret/mes_local_cloud/minio \
    access_key="$MINIO_APP_USER" \
    secret_key="$MINIO_APP_PASSWORD" \
    endpoint="minio:9000" \
    bucket="user-files" \
    use_ssl="false"

echo "✅ MinIO application user credentials stored at secret/mes_local_cloud/minio"
echo "   User: $MINIO_APP_USER (least-privilege access to user-files bucket only)"

# Generate database init script with hashed passwords
echo ""
echo "Generating database initialization script with Vault passwords..."

# Helper function to hash password using werkzeug
hash_password() {
    local password="$1"
    echo "$password" | docker run --rm -i python:3.10-slim sh -c "pip install -q werkzeug && python3 -c \"from werkzeug.security import generate_password_hash; import sys; print(generate_password_hash(sys.stdin.read().strip()), end='')\""
}

# Get passwords from Vault and hash them
echo "Retrieving and hashing passwords..."
ADMIN_PASSWORD=$(vault_exec kv get -field=admin_password secret/mes_local_cloud/app/flask)
ALICE_PASSWORD=$(vault_exec kv get -field=alice_password secret/mes_local_cloud/app/flask)
MOD_PASSWORD=$(vault_exec kv get -field=moderator_password secret/mes_local_cloud/app/flask)

ADMIN_PWD_HASH=$(hash_password "$ADMIN_PASSWORD")
ALICE_PWD_HASH=$(hash_password "$ALICE_PASSWORD")
MOD_PWD_HASH=$(hash_password "$MOD_PASSWORD")

# Generate SQL file
cat > "$PROJECT_ROOT/be_flask/db_init/001_create_users.sql" <<SQLEOF
-- Create users table and seed initial users (admin, alice, moderator)
-- This script is executed by the official Postgres image when the DB directory is empty.
--
-- IMPORTANT: This file is auto-generated by vault/scripts/setup-vault-app.sh
-- Passwords are retrieved from Vault and hashed using werkzeug.security
--
-- To regenerate with updated passwords: Re-run setup-vault-app.sh

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    quota BIGINT NOT NULL DEFAULT 0,
    password_hash VARCHAR(512) NOT NULL
);

-- Insert seed users if they don't exist already
-- Passwords are managed by Vault at secret/mes_local_cloud/app/flask

INSERT INTO users (username, role, quota, password_hash)
SELECT 'admin', 'admin', 0, '${ADMIN_PWD_HASH}'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');

INSERT INTO users (username, role, quota, password_hash)
SELECT 'alice', 'user', 104857600, '${ALICE_PWD_HASH}'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'alice');

INSERT INTO users (username, role, quota, password_hash)
SELECT 'moderator', 'moderator', 0, '${MOD_PWD_HASH}'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'moderator');
SQLEOF

echo "✅ Database initialization script generated"

# Create .env file for application
cat > "$PROJECT_ROOT/.env" <<EOF
# Vault Configuration - Uses Shared Vault Infrastructure
VAULT_ADDR=http://shared_vault_server:8200

# Backend AppRole (Flask application) - mes_local_cloud
VAULT_ROLE_ID=$ROLE_ID
VAULT_SECRET_ID=$SECRET_ID

# Apache AppRole (Frontend web server)
APACHE_VAULT_ROLE_ID=$APACHE_ROLE_ID
APACHE_VAULT_SECRET_ID=$APACHE_SECRET_ID
APACHE_VAULT_AUTH_PATH=approle-apache

# PKI Configuration for Apache
PKI_ENGINE=pki_localhost
PKI_ROLE=apache-server-localhost

# Application Configuration
FLASK_ENV=production
PYTHONUNBUFFERED=1

# PostgreSQL Configuration
# Admin user credentials (for DB initialization only)
POSTGRES_USER=admin
POSTGRES_DB=postgres_db
# App user credentials (Flask connects with these - fetched from Vault)
POSTGRES_APP_USER=flask_app
POSTGRES_APP_PASSWORD=$DB_APP_PASSWORD

# MinIO Root Credentials (for MinIO container administration only)
# These are NOT used by the Flask application
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# MinIO Application User (passed to init script)
# These credentials are also stored in Vault for the Flask app
MINIO_APP_USER=$MINIO_APP_USER
MINIO_APP_PASSWORD=$MINIO_APP_PASSWORD

# MinIO Configuration
MINIO_BUCKET=user-files
MINIO_USE_SSL=false
EOF

echo "✅ .env file created at project root"

# Create secrets directory and database password file for Docker secrets
mkdir -p "$PROJECT_ROOT/secrets"
# Use echo -n to avoid trailing newline which causes authentication issues
echo -n "$DB_ADMIN_PASSWORD" > "$PROJECT_ROOT/secrets/db_password.txt"
chmod 600 "$PROJECT_ROOT/secrets/db_password.txt"
echo "✅ Database admin password file created at secrets/db_password.txt (for DB initialization)"

# Also save credentials for postgres environment
cat > "$PROJECT_ROOT/secrets/postgres.env" <<EOF
POSTGRES_USER=admin
POSTGRES_DB=postgres_db
EOF

echo "✅ PostgreSQL environment file created"

echo ""
echo "==================================="
echo "Vault Setup Complete!"
echo "==================================="
echo ""
echo "📝 Summary:"
echo "   - Connected to shared Vault at: $VAULT_ADDR"
echo "   - Application policies created (mes_local_cloud-app, mes_local_cloud-admin)"
echo "   - AppRole 'mes_local_cloud-flask-app' created"
echo "   - Secrets stored at: secret/mes_local_cloud/"
echo "   - MinIO app user: $MINIO_APP_USER (least-privilege, bucket-only access)"
echo ""
echo "📁 Important files created:"
echo "   - $APP_CREDENTIALS_FILE (AppRole credentials)"
echo "   - $PROJECT_ROOT/.env (Application environment variables)"
echo "   - $PROJECT_ROOT/secrets/db_password.txt (Database password)"
echo "   - $PROJECT_ROOT/be_flask/db_init/001_create_users.sql (DB init script)"
echo ""
echo "⚠️  SECURITY REMINDERS:"
echo "   1. Shared Vault keys are in: ../../vault-infrastructure/scripts/vault-keys.json"
echo "   2. Never commit .env or secrets/ to version control"
echo "   3. Set proper file permissions: chmod 600 .env secrets/*"
echo "   4. Rotate the Secret ID regularly: ./rotate-secret-id.sh"
echo ""
echo "🚀 Next steps:"
echo "   1. Review the .env file"
echo "   2. ⚠️  RESET THE DATABASE to apply user creation:"
echo "      docker compose down -v"
echo "   3. Start the application: docker compose up -d"
echo "   4. Check backend logs: docker compose logs -f backend"
echo ""
