#!/bin/bash
# Setup Keycloak Role in Shared PKI (pki_localhost)
#
# This script creates a role for Keycloak in the existing pki_localhost engine
# that Apache also uses, allowing certificate generation with the same CA.
#
# Prerequisites:
# - Vault must be initialized and unsealed
# - pki_localhost engine must exist (created by Apache setup)
#
# Usage: ./setup-shared-pki-role.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
VAULT_KEYS_FILE="$SCRIPT_DIR/../../vault-infrastructure/scripts/vault-keys.json"
VAULT_CONTAINER="shared_vault_server"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================="
echo "Setup Keycloak Role in Shared PKI"
echo "========================================="
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

echo "🔍 Checking if pki_localhost engine exists..."
# Check if PKI exists
if ! vault_exec secrets list | grep -q "^pki_localhost/"; then
    echo -e "${RED}❌ Error: pki_localhost engine not found${NC}"
    echo "Please run the Apache setup script first:"
    echo "  cd ../../4_three_tier_app/vault/scripts && ./setup-vault-app.sh"
    exit 1
fi

echo -e "${GREEN}✅ pki_localhost engine found${NC}"
echo ""

echo "📋 Creating PKI role for Keycloak..."
# Create role for issuing Keycloak certificates
vault_exec write pki_localhost/roles/keycloak-server-localhost \
    allowed_domains="localhost,keycloak,shared-keycloak-server,*.local,*.keycloak.local" \
    allow_subdomains=true \
    allow_bare_domains=true \
    allow_localhost=true \
    allow_ip_sans=true \
    max_ttl="8760h" \
    ttl="2160h" \
    key_type="rsa" \
    key_bits=2048 \
    require_cn=false

echo -e "${GREEN}✅ PKI role created: keycloak-server-localhost${NC}"
echo ""

echo "🔑 Updating Keycloak policy..."
# Update policy in Vault
POLICY_FILE="$SCRIPT_DIR/../policies/keycloak-policy.hcl"
docker cp "$POLICY_FILE" "$VAULT_CONTAINER:/tmp/keycloak-policy.hcl"
vault_exec policy write keycloak-policy /tmp/keycloak-policy.hcl

echo -e "${GREEN}✅ Keycloak policy updated${NC}"
echo ""

echo "========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  - PKI Engine: pki_localhost (shared with Apache)"
echo "  - Role: keycloak-server-localhost"
echo "  - Allowed domains: localhost, keycloak, shared-keycloak-server, *.local, *.keycloak.local"
echo "  - Default TTL: 90 days"
echo "  - Max TTL: 1 year"
echo "  - Key type: RSA 2048"
echo ""
echo -e "${BLUE}Same CA as Apache:${NC}"
echo "  Both Apache and Keycloak now use certificates from the same CA"
echo "  Clients only need to trust one CA certificate"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Restart Keycloak to generate certificate:"
echo "   docker compose restart keycloak"
echo ""
echo "2. Access Keycloak via HTTPS:"
echo "   https://localhost:8443"
echo ""
echo "3. Get CA certificate (shared with Apache):"
echo "   docker exec shared_vault_server vault read -field=certificate pki_localhost/cert/ca > ca.crt"
