#!/bin/bash
# Vault Unseal Script
#
# This script unseals Vault using the keys stored in vault-keys.json.
# Vault must be unsealed after each restart.
#
# Usage: ./unseal-vault.sh

set -e

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_KEYS_FILE="$SCRIPT_DIR/vault-keys.json"
VAULT_CONTAINER="vault_server"

# Helper function to run vault commands in container
vault_exec() {
    docker exec "$VAULT_CONTAINER" vault "$@"
}

echo "==================================="
echo "Vault Unseal Script"
echo "==================================="
echo ""
echo "Vault Address: $VAULT_ADDR"
echo ""

# Check if vault-keys.json exists
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo "❌ Error: vault-keys.json not found at $VAULT_KEYS_FILE"
    echo "Please run init-vault.sh first to initialize Vault."
    exit 1
fi

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

# Check seal status
SEAL_STATUS=$(vault_exec status -format=json 2>/dev/null | jq -r '.sealed')

if [ "$SEAL_STATUS" = "false" ]; then
    echo "✅ Vault is already unsealed"
    exit 0
fi

echo "Vault is sealed. Unsealing..."

# Read unseal keys from file
UNSEAL_KEY_1=$(jq -r '.unseal_keys_b64[0]' "$VAULT_KEYS_FILE")
UNSEAL_KEY_2=$(jq -r '.unseal_keys_b64[1]' "$VAULT_KEYS_FILE")
UNSEAL_KEY_3=$(jq -r '.unseal_keys_b64[2]' "$VAULT_KEYS_FILE")

# Unseal Vault (requires 3 out of 5 keys)
echo "Applying unseal key 1/3..."
vault_exec operator unseal "$UNSEAL_KEY_1"

echo "Applying unseal key 2/3..."
vault_exec operator unseal "$UNSEAL_KEY_2"

echo "Applying unseal key 3/3..."
vault_exec operator unseal "$UNSEAL_KEY_3"

echo ""
echo "✅ Vault unsealed successfully!"
echo ""
