#!/bin/bash
# Setup Vault PKI for Keycloak TLS Certificates
#
# This script configures Vault's PKI secrets engine to issue certificates for Keycloak.
# After running this script, you can generate certificates from the Vault UI.
#
# Prerequisites:
# - Vault must be initialized and unsealed
#
# Usage: ./setup-vault-pki.sh

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
echo "Setup Vault PKI for Keycloak"
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

echo "🔧 Enabling PKI secrets engine..."
# Enable PKI if not already enabled
if vault_exec secrets list | grep -q "^pki/"; then
    echo -e "${YELLOW}⚠️  PKI already enabled${NC}"
else
    vault_exec secrets enable pki
    echo -e "${GREEN}✅ PKI enabled${NC}"
fi
echo ""

echo "⚙️  Configuring PKI..."
# Tune PKI to allow 10 year certificates
vault_exec secrets tune -max-lease-ttl=87600h pki

# Configure PKI URLs
vault_exec write pki/config/urls \
    issuing_certificates="$VAULT_ADDR/v1/pki/ca" \
    crl_distribution_points="$VAULT_ADDR/v1/pki/crl"

echo -e "${GREEN}✅ PKI configured${NC}"
echo ""

echo "🔐 Generating root CA certificate..."
# Generate root CA (10 year validity)
vault_exec write -field=certificate pki/root/generate/internal \
    common_name="Keycloak Infrastructure Root CA" \
    ttl=87600h > /dev/null 2>&1

echo -e "${GREEN}✅ Root CA generated${NC}"
echo ""

echo "📋 Creating PKI role for Keycloak..."
# Create role for issuing Keycloak certificates
vault_exec write pki/roles/keycloak \
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

echo -e "${GREEN}✅ PKI role created${NC}"
echo ""

echo "🔑 Updating Keycloak policy to include PKI access..."
# Read current policy or create new one
POLICY_FILE="$SCRIPT_DIR/../policies/keycloak-policy.hcl"

# Add PKI permissions to policy
cat > "$POLICY_FILE" << 'EOF'
# Keycloak Policy
# This policy allows read access to Keycloak secrets and PKI certificate generation

# Allow reading Keycloak database credentials
path "secret/data/keycloak/database" {
  capabilities = ["read"]
}

# Allow reading Keycloak admin credentials
path "secret/data/keycloak/admin" {
  capabilities = ["read"]
}

# Allow listing secrets (optional, for debugging)
path "secret/metadata/keycloak/*" {
  capabilities = ["list"]
}

# Allow generating certificates from PKI
path "pki/issue/keycloak" {
  capabilities = ["create", "update"]
}

# Allow reading CA certificate
path "pki/cert/ca" {
  capabilities = ["read"]
}
EOF

# Update policy in Vault
docker cp "$POLICY_FILE" "$VAULT_CONTAINER:/tmp/keycloak-policy.hcl"
vault_exec policy write keycloak-policy /tmp/keycloak-policy.hcl

echo -e "${GREEN}✅ Keycloak policy updated${NC}"
echo ""

echo "========================================="
echo -e "${GREEN}PKI Setup Complete!${NC}"
echo "========================================="
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. Generate certificate from Vault UI:"
echo "   - Navigate to: $VAULT_ADDR"
echo "   - Go to: Secrets > pki > keycloak"
echo "   - Click: 'Generate certificate'"
echo "   - Common Name: localhost (or shared-keycloak-server)"
echo "   - IP SANs: 127.0.0.1"
echo "   - TTL: 90d (or as needed)"
echo ""
echo "2. OR use the fetch-certificates script:"
echo "   ./scripts/fetch-keycloak-certificates.sh"
echo ""
echo "3. Restart Keycloak to apply certificates:"
echo "   docker compose restart keycloak"
echo ""
echo -e "${YELLOW}Certificate Details:${NC}"
echo "  - Role: keycloak"
echo "  - Allowed domains: localhost, *.keycloak.local, etc."
echo "  - Default TTL: 90 days"
echo "  - Max TTL: 1 year"
echo "  - Key type: RSA 2048"
echo ""
echo -e "${YELLOW}Vault UI Access:${NC}"
echo "  - URL: $VAULT_ADDR"
echo "  - Token: $ROOT_TOKEN"
