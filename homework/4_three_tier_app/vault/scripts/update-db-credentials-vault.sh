#!/bin/bash
# Script to update Vault database credentials to use flask_app user
# This updates the existing Vault secret to use least-privilege database user

set -e

echo "======================================================================"
echo "Update Vault Database Credentials - Least Privilege Architecture"
echo "======================================================================"
echo ""
echo "This script updates Vault to store flask_app credentials instead of admin."
echo "Flask application will connect with limited-privilege user."
echo ""

# Get Vault root token
VAULT_ADDR="${VAULT_ADDR:-https://shared_vault_server:8200}"
VAULT_CONTAINER="${VAULT_CONTAINER:-shared_vault_server}"

echo "Checking Vault connection..."
if ! docker ps | grep -q "$VAULT_CONTAINER"; then
    echo "❌ Error: Vault container '$VAULT_CONTAINER' is not running"
    exit 1
fi

echo "✓ Vault container is running"
echo ""

# Get root token from vault keys file (in shared vault infrastructure)
VAULT_KEYS_PATH="/shared/University/system_security/system-security/homework/vault-infrastructure/scripts/vault-keys.json"

if [ ! -f "$VAULT_KEYS_PATH" ]; then
    echo "❌ Error: Vault keys file not found at $VAULT_KEYS_PATH"
    echo "   Trying to read from container..."
    VAULT_TOKEN=$(docker exec "$VAULT_CONTAINER" cat /vault/scripts/vault-keys.json 2>/dev/null | jq -r '.root_token')
else
    VAULT_TOKEN=$(cat "$VAULT_KEYS_PATH" | jq -r '.root_token')
fi

if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
    echo "❌ Error: Could not retrieve Vault root token"
    echo "   Make sure Vault is initialized and vault-keys.json exists"
    exit 1
fi

echo "✓ Retrieved Vault root token"
echo ""

# Update database credentials in Vault
echo "Updating database credentials in Vault..."
docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_ADDR="https://0.0.0.0:8200" -e VAULT_SKIP_VERIFY=1 \
    "$VAULT_CONTAINER" vault kv put secret/mes_local_cloud/database/postgres \
    username="flask_app" \
    password="flask_app_secure_password" \
    database="postgres_db" \
    host="db" \
    port="5432"

echo ""
echo "✅ Vault database credentials updated successfully!"
echo ""
echo "📋 Summary:"
echo "   - Username: flask_app (limited privileges)"
echo "   - Password: flask_app_secure_password"
echo "   - Database: postgres_db"
echo "   - Vault path: secret/mes_local_cloud/database/postgres"
echo ""
echo "🔄 Next steps:"
echo "   1. Restart Flask backend: docker-compose restart backend"
echo "   2. Verify connection: docker-compose logs backend | grep 'Database'"
echo ""
