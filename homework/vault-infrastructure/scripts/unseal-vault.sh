#!/bin/bash
# Unseal Vault Script
# 
# This script unseals the Vault server using the keys stored in vault-keys.json.
# Vault must be unsealed after every restart.
#
# Usage: ./unseal-vault.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_KEYS_FILE="$SCRIPT_DIR/vault-keys.json"
VAULT_CONTAINER="shared_vault_server"

# Helper function to run vault commands in container
vault_exec() {
    docker exec "$VAULT_CONTAINER" vault "$@"
}

echo "==================================="
echo "Unsealing Vault..."
echo "==================================="
echo ""

# Check if Vault container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${VAULT_CONTAINER}$"; then
    echo "❌ Error: Vault container is not running"
    echo "Please start Vault: cd homework/vault-infrastructure && docker compose up -d"
    exit 1
fi

# Check if vault-keys.json exists
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo "❌ Error: vault-keys.json not found"
    echo "Please initialize Vault first: ./init-vault.sh"
    exit 1
fi

# Check if Vault is already unsealed
if vault_exec status 2>&1 | grep -q "Sealed.*false"; then
    echo "ℹ️  Vault is already unsealed"
    exit 0
fi

# Read unseal keys from file
echo "Reading unseal keys from vault-keys.json..."
UNSEAL_KEY_1=$(jq -r '.unseal_keys_b64[0]' "$VAULT_KEYS_FILE")
UNSEAL_KEY_2=$(jq -r '.unseal_keys_b64[1]' "$VAULT_KEYS_FILE")
UNSEAL_KEY_3=$(jq -r '.unseal_keys_b64[2]' "$VAULT_KEYS_FILE")

# Unseal Vault (requires 3 keys)
echo "Unsealing Vault (requires 3 of 5 keys)..."
vault_exec operator unseal "$UNSEAL_KEY_1" > /dev/null
echo "Key 1/3 applied"
vault_exec operator unseal "$UNSEAL_KEY_2" > /dev/null
echo "Key 2/3 applied"
vault_exec operator unseal "$UNSEAL_KEY_3" > /dev/null
echo "Key 3/3 applied"

echo ""
echo "✅ Vault unsealed successfully"
echo ""
