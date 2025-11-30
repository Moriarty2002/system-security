#!/bin/bash
# Store Keycloak Secrets in Vault
#
# This script stores Keycloak credentials in Vault for centralized secret management.
# It reads the credentials from the .env file and stores them in Vault.
#
# Prerequisites:
# - Vault must be initialized and unsealed (run vault-infrastructure/scripts/init-vault.sh)
# - .env file must exist with KEYCLOAK_DB_PASSWORD, KEYCLOAK_ADMIN, KEYCLOAK_ADMIN_PASSWORD
#
# Usage: ./store-secrets-in-vault.sh

set -e

# Simple CLI: support --generate to create .env and generate passwords
GENERATE=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --generate) GENERATE=true; shift ;;
        *) shift ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
VAULT_KEYS_FILE="$SCRIPT_DIR/../../vault-infrastructure/scripts/vault-keys.json"
VAULT_CONTAINER="shared_vault_server"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "==================================="
echo "Store Keycloak Secrets in Vault"
echo "==================================="
echo ""

# Check if Vault container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${VAULT_CONTAINER}$"; then
    echo -e "${RED}❌ Error: Vault container is not running${NC}"
    echo "Please start Vault: cd homework/vault-infrastructure && docker compose up -d"
    exit 1
fi

# Check if vault-keys.json exists
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo -e "${RED}❌ Error: vault-keys.json not found${NC}"
    echo "Please initialize Vault: cd homework/vault-infrastructure/scripts && ./init-vault.sh"
    exit 1
fi

# Get root token
ROOT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE")

# Helper function to run vault commands
vault_exec() {
    docker exec -e VAULT_TOKEN="$ROOT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
}

# If requested, generate .env and credentials
if [ "$GENERATE" = true ]; then
    echo -e "${YELLOW}--generate requested: creating/updating .env with generated credentials${NC}"
    # Backup existing .env if present
    if [ -f "$ENV_FILE" ]; then
        BACKUP="$ENV_FILE.$(date +%s).bak"
        cp "$ENV_FILE" "$BACKUP"
        echo -e "${YELLOW}Existing .env backed up to $BACKUP${NC}"
    else
        mkdir -p "$(dirname "$ENV_FILE")"
        touch "$ENV_FILE"
    fi

    # Generate secure random passwords
    KEYCLOAK_ADMIN=${KEYCLOAK_ADMIN:-admin}
    KEYCLOAK_ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
    KEYCLOAK_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

    # Append/update variables in .env (simple approach: append values)
    cat >> "$ENV_FILE" << EOF
# Keycloak credentials (generated $(date))
KEYCLOAK_ADMIN=$KEYCLOAK_ADMIN
KEYCLOAK_ADMIN_PASSWORD=$KEYCLOAK_ADMIN_PASSWORD
KEYCLOAK_DB_PASSWORD=$KEYCLOAK_DB_PASSWORD
EOF

    echo -e "${GREEN}✓ Generated and wrote Keycloak credentials to $ENV_FILE${NC}"
fi

# Check if .env file exists now
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please run: ./scripts/init-keycloak.sh or use --generate"
    exit 1
fi

# Source .env file
source "$ENV_FILE"

# Verify required variables
if [ -z "$KEYCLOAK_DB_PASSWORD" ] || [ -z "$KEYCLOAK_ADMIN" ] || [ -z "$KEYCLOAK_ADMIN_PASSWORD" ]; then
    echo -e "${RED}❌ Error: Required environment variables not set in .env${NC}"
    exit 1
fi

echo "📥 Reading credentials from .env file..."
echo ""

# Store secrets in Vault
echo "🔐 Storing secrets in Vault..."

vault_exec kv put secret/keycloak/database \
    password="$KEYCLOAK_DB_PASSWORD" \
    username="keycloak" \
    database="keycloak"

vault_exec kv put secret/keycloak/admin \
    username="$KEYCLOAK_ADMIN" \
    password="$KEYCLOAK_ADMIN_PASSWORD"

echo -e "${GREEN}✅ Secrets stored successfully in Vault${NC}"
echo ""
echo "Secrets stored at:"
echo "  - secret/keycloak/database (username, password, database)"
echo "  - secret/keycloak/admin (username, password)"
echo ""

# Verify secrets were stored
echo "🔍 Verifying secrets..."
echo ""

DB_PASSWORD=$(vault_exec kv get -field=password secret/keycloak/database)
ADMIN_USERNAME=$(vault_exec kv get -field=username secret/keycloak/admin)

if [ -n "$DB_PASSWORD" ] && [ -n "$ADMIN_USERNAME" ]; then
    echo -e "${GREEN}✅ Verification successful${NC}"
    echo "  - Database password: [HIDDEN - ${#DB_PASSWORD} characters]"
    echo "  - Admin username: $ADMIN_USERNAME"
else
    echo -e "${RED}❌ Verification failed${NC}"
    exit 1
fi

echo ""
echo "==================================="
echo "Next Steps:"
echo "==================================="
echo "1. Update docker-compose.yaml to fetch secrets from Vault"
echo "2. Remove .env file (secrets now in Vault)"
echo "3. Restart Keycloak: docker compose down && docker compose up -d"
echo ""
echo -e "${YELLOW}⚠️  Note: You can now safely delete the .env file${NC}"
echo -e "${YELLOW}   Backup command: mv .env .env.backup${NC}"
