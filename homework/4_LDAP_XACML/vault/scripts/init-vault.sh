#!/bin/bash
# Vault Initialization Script
# 
# This script initializes a new Vault server, unseals it, and configures
# the necessary secrets, policies, and authentication methods for the application.
#
# SECURITY WARNING: This script outputs sensitive information (unseal keys, root token).
# In production, use secure key management practices and store these values safely.
#
# Usage: ./init-vault.sh

set -e

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_KEYS_FILE="$SCRIPT_DIR/vault-keys.json"
VAULT_CONTAINER="vault_server"
VAULT_TOKEN=""

# Helper function to run vault commands in container
vault_exec() {
    if [ -n "$VAULT_TOKEN" ]; then
        docker exec -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault "$@"
    else
        docker exec "$VAULT_CONTAINER" vault "$@"
    fi
}

echo "==================================="
echo "Vault Initialization Script"
echo "==================================="
echo ""
echo "Vault Address: $VAULT_ADDR"
echo ""

# Check if Vault container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${VAULT_CONTAINER}$"; then
    echo "❌ Error: Vault container is not running"
    echo "Please start Vault: docker compose -f docker-compose.vault.yaml up -d"
    exit 1
fi

# Check if Vault is accessible
if ! curl -s "$VAULT_ADDR/v1/sys/health" > /dev/null 2>&1; then
    echo "❌ Error: Vault is not accessible at $VAULT_ADDR"
    echo "Please ensure Vault is running: docker compose -f docker-compose.vault.yaml up -d"
    exit 1
fi

# Check if Vault is already initialized
if vault_exec status 2>&1 | grep -q "Initialized.*true"; then
    echo "⚠️  Vault is already initialized."
    echo ""
    
    if [ -f "$VAULT_KEYS_FILE" ]; then
        echo "Found existing vault-keys.json. Attempting to unseal..."
        
        # Read unseal keys from file
        UNSEAL_KEY_1=$(jq -r '.unseal_keys_b64[0]' "$VAULT_KEYS_FILE")
        UNSEAL_KEY_2=$(jq -r '.unseal_keys_b64[1]' "$VAULT_KEYS_FILE")
        UNSEAL_KEY_3=$(jq -r '.unseal_keys_b64[2]' "$VAULT_KEYS_FILE")
        
        # Unseal Vault
        vault_exec operator unseal "$UNSEAL_KEY_1" > /dev/null
        vault_exec operator unseal "$UNSEAL_KEY_2" > /dev/null
        vault_exec operator unseal "$UNSEAL_KEY_3" > /dev/null
        
        echo "✅ Vault unsealed successfully"
        
        # Export root token
        ROOT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE")
        export VAULT_TOKEN="$ROOT_TOKEN"
        echo "✅ Root token loaded from vault-keys.json"
    else
        echo "❌ Error: vault-keys.json not found. Cannot unseal automatically."
        echo "Please unseal Vault manually with your unseal keys."
        exit 1
    fi
else
    echo "Initializing Vault..."
    
    # Initialize Vault with 5 key shares and 3 keys required to unseal
    vault_exec operator init -key-shares=5 -key-threshold=3 -format=json > "$VAULT_KEYS_FILE"
    
    echo "✅ Vault initialized successfully"
    echo ""
    echo "⚠️  IMPORTANT: Unseal keys and root token saved to: $VAULT_KEYS_FILE"
    echo "⚠️  Keep this file secure and back it up! You'll need it to unseal Vault."
    echo ""
    
    # Read unseal keys and root token
    UNSEAL_KEY_1=$(jq -r '.unseal_keys_b64[0]' "$VAULT_KEYS_FILE")
    UNSEAL_KEY_2=$(jq -r '.unseal_keys_b64[1]' "$VAULT_KEYS_FILE")
    UNSEAL_KEY_3=$(jq -r '.unseal_keys_b64[2]' "$VAULT_KEYS_FILE")
    ROOT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE")
    
    # Unseal Vault
    echo "Unsealing Vault..."
    vault_exec operator unseal "$UNSEAL_KEY_1" > /dev/null
    vault_exec operator unseal "$UNSEAL_KEY_2" > /dev/null
    vault_exec operator unseal "$UNSEAL_KEY_3" > /dev/null
    
    echo "✅ Vault unsealed successfully"
    
    # Set root token for subsequent commands
    VAULT_TOKEN="$ROOT_TOKEN"
fi

echo ""
echo "==================================="
echo "Configuring Vault..."
echo "==================================="
echo ""

# Enable KV v2 secrets engine
echo "Enabling KV v2 secrets engine..."
if ! vault_exec secrets list | grep -q "^secret/"; then
    vault_exec secrets enable -path=secret kv-v2
    echo "✅ KV v2 secrets engine enabled at 'secret/'"
else
    echo "ℹ️  KV v2 secrets engine already enabled"
fi

# Write application policies
echo ""
echo "Creating application policy..."
docker exec -i -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault policy write app-policy - < "$SCRIPT_DIR/../policies/app-policy.hcl"
echo "✅ Application policy created"

echo ""
echo "Creating admin policy..."
docker exec -i -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault policy write admin-policy - < "$SCRIPT_DIR/../policies/admin-policy.hcl"
echo "✅ Admin policy created"

# Enable AppRole authentication
echo ""
echo "Enabling AppRole authentication..."
if ! vault_exec auth list | grep -q "^approle/"; then
    vault_exec auth enable approle
    echo "✅ AppRole authentication enabled"
else
    echo "ℹ️  AppRole authentication already enabled"
fi

# Create AppRole for Flask application
echo ""
echo "Creating AppRole for Flask application..."
vault_exec write auth/approle/role/flask-app \
    token_policies="app-policy" \
    token_ttl=1h \
    token_max_ttl=4h \
    bind_secret_id=true \
    secret_id_ttl=0

echo "✅ AppRole 'flask-app' created"

# Get Role ID and Secret ID
ROLE_ID=$(vault_exec read -field=role_id auth/approle/role/flask-app/role-id)
SECRET_ID=$(vault_exec write -field=secret_id -f auth/approle/role/flask-app/secret-id)

# Save AppRole credentials
cat > "$SCRIPT_DIR/approle-credentials.txt" <<EOF
Flask Application AppRole Credentials
======================================
Role ID: $ROLE_ID
Secret ID: $SECRET_ID

⚠️  IMPORTANT: Store these credentials securely!
⚠️  The Secret ID is only shown once and should be provided to the Flask application.
⚠️  Add these to your .env file or environment variables.
EOF

echo "✅ AppRole credentials saved to: $SCRIPT_DIR/approle-credentials.txt"

# Generate secure secrets
echo ""
echo "==================================="
echo "Generating and storing secrets..."
echo "==================================="
echo ""

# Generate a secure JWT secret key
JWT_SECRET=$(openssl rand -base64 32)
echo "Generated JWT secret key..."

# Generate secure database password
DB_PASSWORD=$(openssl rand -base64 24)
echo "Generated database password..."

# Store application secrets
vault_exec kv put secret/app/flask \
    jwt_secret="$JWT_SECRET" \
    admin_password="admin123" \
    alice_password="alice123" \
    moderator_password="moderator123"

echo "✅ Application secrets stored at secret/app/flask"

# Store database secrets
vault_exec kv put secret/database/postgres \
    username="admin" \
    password="$DB_PASSWORD" \
    database="postgres_db" \
    host="db" \
    port="5432"

echo "✅ Database secrets stored at secret/database/postgres"

# Create .env file for application
cat > "$SCRIPT_DIR/../../.env" <<EOF
# Vault Configuration
VAULT_ADDR=http://vault_server:8200
VAULT_ROLE_ID=$ROLE_ID
VAULT_SECRET_ID=$SECRET_ID

# Application Configuration
FLASK_ENV=production
PYTHONUNBUFFERED=1
EOF

echo "✅ .env file created at project root"

# Create secrets directory and database password file for Docker secrets
mkdir -p "$SCRIPT_DIR/../../secrets"
echo "$DB_PASSWORD" > "$SCRIPT_DIR/../../secrets/db_password.txt"
chmod 600 "$SCRIPT_DIR/../../secrets/db_password.txt"
echo "✅ Database password file created at secrets/db_password.txt"

# Also save credentials for postgres environment
cat > "$SCRIPT_DIR/../../secrets/postgres.env" <<EOF
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
echo "   - Vault initialized and unsealed"
echo "   - KV v2 secrets engine enabled"
echo "   - Application and admin policies created"
echo "   - AppRole authentication configured"
echo "   - Secrets generated and stored"
echo ""
echo "📁 Important files created:"
echo "   - $VAULT_KEYS_FILE (Unseal keys & root token)"
echo "   - $SCRIPT_DIR/approle-credentials.txt (AppRole credentials)"
echo "   - $SCRIPT_DIR/../../.env (Application environment variables)"
echo "   - $SCRIPT_DIR/../../secrets/db_password.txt (Database password)"
echo ""
echo "⚠️  SECURITY REMINDERS:"
echo "   1. Keep vault-keys.json secure and backed up"
echo "   2. Never commit these files to version control"
echo "   3. Set proper file permissions: chmod 600 .env secrets/*"
echo "   4. Rotate the Secret ID regularly"
echo "   5. In production, use more secure key storage (HSM, KMS)"
echo ""
echo "🚀 Next steps:"
echo "   1. Review the .env file"
echo "   2. Verify secrets directory: ls -la secrets/"
echo "   3. Start the application: docker compose up -d"
echo "   4. Check backend logs: docker compose logs -f backend"
echo "   5. Access Vault UI at: $VAULT_ADDR"
echo "      Login with token: $ROOT_TOKEN"
echo ""
echo "📖 For detailed information, see: VAULT_INTEGRATION.md"
echo ""
