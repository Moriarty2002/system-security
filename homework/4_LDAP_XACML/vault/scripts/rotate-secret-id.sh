#!/bin/bash
# Rotate AppRole Secret ID
#
# This script generates a new Secret ID for the Flask application AppRole.
# Run this periodically to rotate credentials following security best practices.
#
# Usage: ./rotate-secret-id.sh

set -e

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_KEYS_FILE="$SCRIPT_DIR/vault-keys.json"
VAULT_CONTAINER="vault_server"

# Helper function to run vault commands in container with token
vault_exec() {
    docker exec -e VAULT_TOKEN="$VAULT_TOKEN" "$VAULT_CONTAINER" vault "$@"
}

echo "==================================="
echo "Rotate AppRole Secret ID"
echo "==================================="
echo ""

# Check if vault-keys.json exists
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo "❌ Error: vault-keys.json not found"
    echo "Please run init-vault.sh first."
    exit 1
fi

# Check if Vault container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${VAULT_CONTAINER}$"; then
    echo "❌ Error: Vault container is not running"
    echo "Please start Vault: docker compose -f docker-compose.vault.yaml up -d"
    exit 1
fi

# Get root token
ROOT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE")
VAULT_TOKEN="$ROOT_TOKEN"

# Check if Vault is unsealed
SEAL_STATUS=$(vault_exec status -format=json 2>/dev/null | jq -r '.sealed')
if [ "$SEAL_STATUS" = "true" ]; then
    echo "❌ Error: Vault is sealed"
    echo "Please unseal Vault first: ./unseal-vault.sh"
    exit 1
fi

echo "Generating new Secret ID for flask-app AppRole..."
echo ""

# Generate new Secret ID
NEW_SECRET_ID=$(vault_exec write -field=secret_id -f auth/approle/role/flask-app/secret-id)
ROLE_ID=$(vault_exec read -field=role_id auth/approle/role/flask-app/role-id)

echo "✅ New Secret ID generated"
echo ""
echo "==================================="
echo "Updated Credentials"
echo "==================================="
echo "Role ID: $ROLE_ID"
echo "New Secret ID: $NEW_SECRET_ID"
echo ""
echo "⚠️  Update your .env file with the new VAULT_SECRET_ID"
echo "⚠️  Restart the Flask application after updating"
echo ""

# Save to file
cat > "$SCRIPT_DIR/approle-credentials.txt" <<EOF
Flask Application AppRole Credentials (Rotated: $(date))
==========================================================
Role ID: $ROLE_ID
Secret ID: $NEW_SECRET_ID

⚠️  IMPORTANT: Update the VAULT_SECRET_ID in your .env file
⚠️  Restart the application after updating: docker compose restart backend
EOF

echo "✅ Credentials saved to: $SCRIPT_DIR/approle-credentials.txt"
echo ""
