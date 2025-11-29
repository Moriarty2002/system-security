#!/bin/bash
# Setup Vault Authentication for Keycloak
#
# This script creates an AppRole authentication for Keycloak to access its secrets.
# Similar to the application's AppRole setup, but for the Keycloak infrastructure itself.
#
# Prerequisites:
# - Vault must be initialized and unsealed
# - Secrets must be stored in Vault (run ./store-secrets-in-vault.sh first)
#
# Usage: ./setup-vault-approle.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
VAULT_KEYS_FILE="$SCRIPT_DIR/../../vault-infrastructure/scripts/vault-keys.json"
VAULT_CONTAINER="shared_vault_server"
CREDENTIALS_FILE="$SCRIPT_DIR/approle-credentials.txt"
POLICY_FILE="$SCRIPT_DIR/../policies/keycloak-policy.hcl"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "==================================="
echo "Setup Vault AppRole for Keycloak"
echo "==================================="
echo ""

# Check if Vault container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${VAULT_CONTAINER}$"; then
    echo -e "${RED}❌ Error: Vault container is not running${NC}"
    exit 1
fi

# Check if vault-keys.json exists
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo -e "${RED}❌ Error: vault-keys.json not found${NC}"
    echo "Please initialize Vault first"
    exit 1
fi

# Get root token
ROOT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE")

# Helper function to run vault commands
vault_exec() {
    docker exec -e VAULT_TOKEN="$ROOT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
}

# Check if policy file exists
if [ ! -f "$POLICY_FILE" ]; then
    echo -e "${RED}❌ Error: Policy file not found at $POLICY_FILE${NC}"
    exit 1
fi

echo "📋 Creating Keycloak policy..."
# Copy policy to container and create it
docker cp "$POLICY_FILE" "$VAULT_CONTAINER:/tmp/keycloak-policy.hcl"
vault_exec policy write keycloak-policy /tmp/keycloak-policy.hcl
echo -e "${GREEN}✅ Policy created${NC}"
echo ""

echo "🔐 Enabling AppRole authentication..."
# Enable AppRole if not already enabled
if ! vault_exec auth list | grep -q "approle/"; then
    vault_exec auth enable approle
    echo -e "${GREEN}✅ AppRole enabled${NC}"
else
    echo -e "${YELLOW}⚠️  AppRole already enabled${NC}"
fi
echo ""

echo "👤 Creating Keycloak AppRole..."
vault_exec write auth/approle/role/keycloak \
    token_policies="keycloak-policy" \
    token_ttl=1h \
    token_max_ttl=4h \
    secret_id_ttl=0 \
    secret_id_num_uses=0
echo -e "${GREEN}✅ AppRole created${NC}"
echo ""

echo "🔑 Generating credentials..."
ROLE_ID=$(vault_exec read -field=role_id auth/approle/role/keycloak/role-id)
SECRET_ID=$(vault_exec write -field=secret_id -f auth/approle/role/keycloak/secret-id)

# Save credentials
cat > "$CREDENTIALS_FILE" << EOF
# Keycloak Vault AppRole Credentials
# Generated: $(date)
# 
# These credentials allow Keycloak containers to authenticate with Vault
# and retrieve secrets.

VAULT_ROLE_ID=$ROLE_ID
VAULT_SECRET_ID=$SECRET_ID
VAULT_ADDR=https://shared_vault_server:8200

# How to use in docker-compose.yaml:
# environment:
#   VAULT_ADDR: https://shared_vault_server:8200
#   VAULT_ROLE_ID: $ROLE_ID
#   VAULT_SECRET_ID: $SECRET_ID
EOF

chmod 600 "$CREDENTIALS_FILE"

echo -e "${GREEN}✅ Credentials generated${NC}"
echo ""
echo "Credentials saved to: $CREDENTIALS_FILE"
echo ""
echo "Role ID:    $ROLE_ID"
echo "Secret ID:  [HIDDEN - saved in file]"
echo ""

echo "==================================="
echo "Next Steps:"
echo "==================================="
echo "1. Update docker-compose.yaml to use Vault agent or fetch secrets at startup"
echo "2. Add init container or entrypoint script to fetch secrets from Vault"
echo "3. Test the setup with: docker compose up"
echo ""
echo -e "${YELLOW}⚠️  Security Note:${NC}"
echo "   - Keep approle-credentials.txt secure (chmod 600)"
echo "   - Consider using Vault agent sidecar for automatic secret rotation"
echo "   - In production, use short-lived tokens and secret rotation"
