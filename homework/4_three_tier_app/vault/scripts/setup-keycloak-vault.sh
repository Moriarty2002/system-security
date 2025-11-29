#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Keycloak Configuration for Vault ===${NC}"
echo ""

# Check if Vault is running
if ! docker ps | grep -q shared_vault_server; then
    echo -e "${RED}Error: Vault server is not running${NC}"
    echo "Please start the Vault infrastructure first:"
    echo "  cd ../../vault-infrastructure && docker compose up -d"
    exit 1
fi

# Source the Vault token (from vault-infrastructure setup)
VAULT_KEYS_FILE="../../../vault-infrastructure/scripts/vault-keys.json"
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo -e "${RED}Error: Vault keys file not found at $VAULT_KEYS_FILE${NC}"
    echo "Please initialize Vault first by running:"
    echo "  cd ../../../vault-infrastructure/scripts && ./init-vault.sh"
    exit 1
fi

export VAULT_ADDR='https://127.0.0.1:8200'
export VAULT_SKIP_VERIFY=1
export VAULT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE")

# Define vault command alias (use docker exec)
VAULT_CMD="docker exec -e VAULT_TOKEN=$VAULT_TOKEN -e VAULT_ADDR=$VAULT_ADDR -e VAULT_SKIP_VERIFY=$VAULT_SKIP_VERIFY shared_vault_server vault"

echo -e "${YELLOW}Configuring Keycloak secrets in Vault...${NC}"

# Generate secure Keycloak admin password
KEYCLOAK_ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
KEYCLOAK_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# Store Keycloak configuration in Vault
$VAULT_CMD kv put secret/mes_local_cloud/keycloak \
    server_url="http://keycloak:8080" \
    realm="mes-local-cloud" \
    client_id="mes-local-cloud-api" \
    client_secret="" \
    admin_username="admin" \
    admin_password="$KEYCLOAK_ADMIN_PASSWORD"

echo -e "${GREEN}✓ Keycloak secrets stored in Vault${NC}"

# Store Keycloak database credentials
$VAULT_CMD kv put secret/mes_local_cloud/keycloak/database \
    username="keycloak_user" \
    password="$KEYCLOAK_DB_PASSWORD"

echo -e "${GREEN}✓ Keycloak database credentials stored in Vault${NC}"

# Update .env file with Keycloak configuration
ENV_FILE="../../.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    touch "$ENV_FILE"
fi

# Add or update Keycloak environment variables
echo "" >> "$ENV_FILE"
echo "# Keycloak Configuration" >> "$ENV_FILE"
echo "KEYCLOAK_ADMIN=admin" >> "$ENV_FILE"
echo "KEYCLOAK_ADMIN_PASSWORD=$KEYCLOAK_ADMIN_PASSWORD" >> "$ENV_FILE"
echo "KEYCLOAK_DB_USER=keycloak_user" >> "$ENV_FILE"
echo "KEYCLOAK_DB_PASSWORD=$KEYCLOAK_DB_PASSWORD" >> "$ENV_FILE"
echo "KEYCLOAK_REALM=mes-local-cloud" >> "$ENV_FILE"
echo "KEYCLOAK_CLIENT_ID=mes-local-cloud-api" >> "$ENV_FILE"
echo "KEYCLOAK_SERVER_URL=http://keycloak:8080" >> "$ENV_FILE"

echo -e "${GREEN}✓ Environment variables updated in .env${NC}"

echo ""
echo -e "${GREEN}=== Keycloak Configuration Complete ===${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Start the application stack:"
echo "   cd ../../4_three_tier_app && docker compose up -d"
echo ""
echo "2. Access Keycloak Admin Console:"
echo "   URL: http://localhost:8080"
echo "   Username: admin"
echo "   Password: $KEYCLOAK_ADMIN_PASSWORD"
echo ""
echo "3. Configure Keycloak:"
echo "   - Create realm: mes-local-cloud"
echo "   - Create client: mes-local-cloud-api"
echo "   - Create users and assign roles (admin, moderator, user)"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC} Save the Keycloak admin password securely!"
echo ""
