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
docker exec -i -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault policy write 4_ldap_xacml-app - < "$SCRIPT_DIR/../policies/app-policy.hcl"
echo "✅ Application policy created"

echo ""
echo "Creating admin-policy for 4_three_tier_app..."
docker exec -i -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault policy write 4_ldap_xacml-admin - < "$SCRIPT_DIR/../policies/admin-policy.hcl"
echo "✅ Admin policy created"

# Create AppRole for Flask application
echo ""
echo "==================================="
echo "Creating AppRole..."
echo "==================================="
echo ""

echo "Creating AppRole for 4_three_tier_app Flask application..."
vault_exec write auth/approle/role/4_ldap_xacml-flask-app \
    token_policies="4_ldap_xacml-app" \
    token_ttl=1h \
    token_max_ttl=4h \
    bind_secret_id=true \
    secret_id_ttl=0

echo "✅ AppRole '4_ldap_xacml-flask-app' created"

# Get Role ID and Secret ID
ROLE_ID=$(vault_exec read -field=role_id auth/approle/role/4_ldap_xacml-flask-app/role-id)
SECRET_ID=$(vault_exec write -field=secret_id -f auth/approle/role/4_ldap_xacml-flask-app/secret-id)

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

# Use fixed password for development (change for production!)
DB_PASSWORD="devpass123_NeverUseInProduction"
echo "Using fixed development database password..."

# Store application secrets in namespaced path
vault_exec kv put secret/4_ldap_xacml/app/flask \
    jwt_secret="$JWT_SECRET" \
    admin_password="admin" \
    alice_password="alice" \
    moderator_password="moderator"

echo "✅ Application secrets stored at secret/4_ldap_xacml/app/flask"

# Store database secrets in namespaced path
vault_exec kv put secret/4_ldap_xacml/database/postgres \
    username="admin" \
    password="$DB_PASSWORD" \
    database="postgres_db" \
    host="db" \
    port="5432"

echo "✅ Database secrets stored at secret/4_ldap_xacml/database/postgres"

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
ADMIN_PASSWORD=$(vault_exec kv get -field=admin_password secret/4_ldap_xacml/app/flask)
ALICE_PASSWORD=$(vault_exec kv get -field=alice_password secret/4_ldap_xacml/app/flask)
MOD_PASSWORD=$(vault_exec kv get -field=moderator_password secret/4_ldap_xacml/app/flask)

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
-- Passwords are managed by Vault at secret/4_ldap_xacml/app/flask

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
VAULT_ROLE_ID=$ROLE_ID
VAULT_SECRET_ID=$SECRET_ID

# Application Configuration
FLASK_ENV=production
PYTHONUNBUFFERED=1
EOF

echo "✅ .env file created at project root"

# Create secrets directory and database password file for Docker secrets
mkdir -p "$PROJECT_ROOT/secrets"
# Use echo -n to avoid trailing newline which causes authentication issues
echo -n "$DB_PASSWORD" > "$PROJECT_ROOT/secrets/db_password.txt"
chmod 600 "$PROJECT_ROOT/secrets/db_password.txt"
echo "✅ Database password file created at secrets/db_password.txt"

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
echo "   - Application policies created (4_ldap_xacml-app, 4_ldap_xacml-admin)"
echo "   - AppRole '4_ldap_xacml-flask-app' created"
echo "   - Secrets stored at: secret/4_ldap_xacml/"
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
