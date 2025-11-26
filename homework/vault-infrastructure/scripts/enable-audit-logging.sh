#!/bin/bash
# Enable Audit Logging on Vault
# 
# This script enables file-based audit logging on the shared Vault server.
# Audit logs record all requests and responses to Vault for security monitoring.
#
# Prerequisites:
#   - Vault must be running and unsealed
#   - You must have root token or appropriate permissions
#
# Usage: ./enable-audit-logging.sh

set -e

VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_KEYS_FILE="$SCRIPT_DIR/vault-keys.json"
VAULT_CONTAINER="shared_vault_server"
AUDIT_LOG_PATH="/vault/logs/audit.log"

# Helper function to run vault commands in container
vault_exec() {
    if [ -n "$VAULT_TOKEN" ]; then
        docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
    else
        docker exec -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
    fi
}

echo "==================================="
echo "Enable Vault Audit Logging"
echo "==================================="
echo ""
echo "Vault Address: $VAULT_ADDR"
echo ""

# Check if Vault container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${VAULT_CONTAINER}$"; then
    echo "❌ Error: Vault container is not running"
    echo "Please start Vault: cd homework/vault-infrastructure && docker compose up -d"
    exit 1
fi

# Check if vault-keys.json exists
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo "❌ Error: vault-keys.json not found at $VAULT_KEYS_FILE"
    echo "Please initialize Vault first: ./init-vault.sh"
    exit 1
fi

# Get root token
ROOT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE")
VAULT_TOKEN="$ROOT_TOKEN"

# Check if Vault is unsealed
if vault_exec status 2>&1 | grep -q "Sealed.*true"; then
    echo "❌ Error: Vault is sealed"
    echo "Please unseal Vault: ./unseal-vault.sh"
    exit 1
fi

echo "✅ Connected to Vault"
echo ""

# Check if audit logging is already enabled
echo "Checking current audit devices..."
AUDIT_LIST=$(vault_exec audit list 2>&1 || echo "")

if echo "$AUDIT_LIST" | grep -q "file/"; then
    echo "⚠️  Audit logging is already enabled"
    echo ""
    echo "Current audit devices:"
    vault_exec audit list
    echo ""
    read -p "Do you want to disable and re-enable it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing audit configuration"
        exit 0
    fi
    
    echo "Disabling existing audit device..."
    vault_exec audit disable file/
fi

# Enable audit logging
echo "Enabling file-based audit logging..."
vault_exec audit enable file file_path="$AUDIT_LOG_PATH"

echo ""
echo "✅ Audit logging enabled successfully!"
echo ""
echo "Audit log location: $AUDIT_LOG_PATH"
echo "Inside container: /vault/logs/audit.log"
echo "On host: ./logs/audit.log"
echo ""
echo "To view audit logs:"
echo "  tail -f ./logs/audit.log"
echo ""
echo "To view formatted audit logs:"
echo "  cat ./logs/audit.log | jq"
echo ""
echo "⚠️  Note: Audit logs contain sensitive information."
echo "    Ensure proper access controls and rotation policies."
echo ""
