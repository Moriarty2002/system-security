#!/bin/bash
# Shared Vault Initialization Script
# 
# This script initializes the shared Vault server that can be used by multiple applications.
# It sets up the basic infrastructure (KV secrets engine, auth methods) but application-specific
# configuration should be done by each application.
#
# SECURITY WARNING: This script outputs sensitive information (unseal keys, root token).
# In production, use secure key management practices and store these values safely.
#
# Usage: ./init-vault.sh

set -e

VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_KEYS_FILE="$SCRIPT_DIR/vault-keys.json"
VAULT_CONTAINER="shared_vault_server"
VAULT_TOKEN=""

# Helper function to run vault commands in container
vault_exec() {
    if [ -n "$VAULT_TOKEN" ]; then
        docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
    else
        docker exec -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
    fi
}

echo "==================================="
echo "Shared Vault Initialization"
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

# Check if Vault is accessible
if ! curl -sk "$VAULT_ADDR/v1/sys/health" > /dev/null 2>&1; then
    echo "❌ Error: Vault is not accessible at $VAULT_ADDR"
    echo "Please ensure Vault is running and accessible"
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

# Enable AppRole authentication
echo ""
echo "Enabling AppRole authentication..."
if ! vault_exec auth list | grep -q "^approle/"; then
    vault_exec auth enable approle
    echo "✅ AppRole authentication enabled"
else
    echo "ℹ️  AppRole authentication already enabled"
fi

echo ""
echo "==================================="
echo "Vault Setup Complete!"
echo "==================================="
echo ""
echo "📝 Summary:"
echo "   - Vault initialized and unsealed"
echo "   - KV v2 secrets engine enabled at 'secret/'"
echo "   - AppRole authentication enabled"
echo ""
echo "📁 Important files created:"
echo "   - $VAULT_KEYS_FILE (Unseal keys & root token)"
echo ""
echo "⚠️  SECURITY REMINDERS:"
echo "   1. Keep vault-keys.json secure and backed up"
echo "   2. Never commit this file to version control"
echo "   3. Set proper file permissions: chmod 600 vault-keys.json"
echo "   4. In production, use more secure key storage (HSM, KMS)"
echo ""
echo "🚀 Next steps:"
echo "   1. Access Vault UI at: $VAULT_ADDR"
echo "      Login with root token: $ROOT_TOKEN"
echo "   2. Each application should configure its own:"
echo "      - Policies (in policies/ folder)"
echo "      - AppRoles (for authentication)"
echo "      - Secrets (in appropriate secret/ paths)"
echo "   3. Use application-specific setup scripts to configure Vault for each app"
echo ""
echo "📖 Applications using this Vault:"
echo "   - homework/4_LDAP_XACML (File Storage Service)"
echo "   - (Add more applications as needed)"
echo ""
