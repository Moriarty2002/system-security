#!/bin/bash
# Fetch Keycloak TLS Certificates from Vault PKI
#
# This script generates a new certificate from Vault PKI and saves it to the certs/ directory.
# The certificate is automatically picked up by Keycloak on next restart.
#
# Prerequisites:
# - Vault PKI must be configured (run ./setup-vault-pki.sh first)
# - Keycloak AppRole must have PKI permissions
#
# Usage: ./fetch-keycloak-certificates.sh [common_name] [ttl]
#   common_name: Domain name for certificate (default: localhost)
#   ttl: Certificate validity period (default: 2160h = 90 days)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/../certs"
VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
VAULT_KEYS_FILE="$SCRIPT_DIR/../../vault-infrastructure/scripts/vault-keys.json"
VAULT_CONTAINER="shared_vault_server"
APPROLE_FILE="$SCRIPT_DIR/approle-credentials.txt"

# Parameters
COMMON_NAME="${1:-localhost}"
TTL="${2:-2160h}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================="
echo "Fetch Keycloak Certificates from Vault"
echo "========================================="
echo ""

# Create certs directory if it doesn't exist
mkdir -p "$CERTS_DIR"

# Check if Vault container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${VAULT_CONTAINER}$"; then
    echo -e "${RED}❌ Error: Vault container is not running${NC}"
    exit 1
fi

# Get authentication token
if [ -f "$APPROLE_FILE" ]; then
    echo "🔐 Authenticating with Vault using AppRole..."
    source "$APPROLE_FILE"
    VAULT_TOKEN=$(docker exec -e VAULT_ADDR="$VAULT_ADDR" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" \
        vault write -field=token auth/approle/login \
        role_id="$VAULT_ROLE_ID" \
        secret_id="$VAULT_SECRET_ID")
elif [ -f "$VAULT_KEYS_FILE" ]; then
    echo "🔐 Using root token..."
    VAULT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE")
else
    echo -e "${RED}❌ Error: No authentication method available${NC}"
    exit 1
fi

if [ -z "$VAULT_TOKEN" ]; then
    echo -e "${RED}❌ Error: Failed to authenticate with Vault${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Authenticated${NC}"
echo ""

# Helper function
vault_exec() {
    docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
}

echo "📋 Requesting certificate..."
echo "  Common Name: $COMMON_NAME"
echo "  TTL: $TTL"
echo ""

# Generate certificate
CERT_DATA=$(vault_exec write -format=json pki/issue/keycloak \
    common_name="$COMMON_NAME" \
    alt_names="shared-keycloak-server,keycloak,localhost" \
    ip_sans="127.0.0.1" \
    ttl="$TTL")

# Extract certificate components
echo "$CERT_DATA" | jq -r '.data.certificate' > "$CERTS_DIR/keycloak.crt"
echo "$CERT_DATA" | jq -r '.data.private_key' > "$CERTS_DIR/keycloak.key"
echo "$CERT_DATA" | jq -r '.data.ca_chain[]' > "$CERTS_DIR/ca.crt"
echo "$CERT_DATA" | jq -r '.data.issuing_ca' >> "$CERTS_DIR/ca.crt"

# Create full chain (certificate + CA)
cat "$CERTS_DIR/keycloak.crt" "$CERTS_DIR/ca.crt" > "$CERTS_DIR/keycloak-fullchain.crt"

# Set restrictive permissions
chmod 600 "$CERTS_DIR/keycloak.key"
chmod 644 "$CERTS_DIR/keycloak.crt"
chmod 644 "$CERTS_DIR/ca.crt"
chmod 644 "$CERTS_DIR/keycloak-fullchain.crt"

# Extract certificate details
SERIAL=$(echo "$CERT_DATA" | jq -r '.data.serial_number')
EXPIRATION=$(echo "$CERT_DATA" | jq -r '.data.expiration')
EXPIRATION_DATE=$(date -d "@$EXPIRATION" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -r "$EXPIRATION" '+%Y-%m-%d %H:%M:%S')

echo -e "${GREEN}✅ Certificate generated successfully${NC}"
echo ""
echo "Certificate Details:"
echo "  Common Name: $COMMON_NAME"
echo "  Serial: $SERIAL"
echo "  Expires: $EXPIRATION_DATE"
echo ""
echo "Files created in $CERTS_DIR/:"
echo "  - keycloak.crt          (certificate)"
echo "  - keycloak.key          (private key)"
echo "  - ca.crt                (CA certificate)"
echo "  - keycloak-fullchain.crt (certificate + CA chain)"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Restart Keycloak to apply new certificates:"
echo "   docker compose restart keycloak"
echo ""
echo "2. Access Keycloak via HTTPS:"
echo "   https://localhost:8443"
echo ""
echo -e "${BLUE}Note: Browser will trust this certificate after importing CA${NC}"
echo "Import CA certificate from: $CERTS_DIR/ca.crt"
