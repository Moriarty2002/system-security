#!/bin/bash
# Keycloak Entrypoint with Vault Integration
#
# This script fetches secrets from Vault using AppRole authentication
# and then starts Keycloak with the retrieved credentials.

set -e

VAULT_ADDR="${VAULT_ADDR:-https://shared_vault_server:8200}"
VAULT_ROLE_ID="${VAULT_ROLE_ID}"
VAULT_SECRET_ID="${VAULT_SECRET_ID}"

echo "========================================="
echo "Keycloak Startup - Fetching Vault Secrets"
echo "========================================="

# Validate required environment variables
if [ -z "$VAULT_ROLE_ID" ] || [ -z "$VAULT_SECRET_ID" ]; then
    echo "❌ ERROR: VAULT_ROLE_ID and VAULT_SECRET_ID must be set"
    exit 1
fi

# Export Vault address and skip verify for self-signed cert
export VAULT_ADDR

echo "🔐 Authenticating with Vault..."

# Authenticate with Vault using AppRole and the Vault CLI
VAULT_TOKEN=$(vault write -field=token auth/approle/login \
    role_id="$VAULT_ROLE_ID" \
    secret_id="$VAULT_SECRET_ID")

if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
    echo "❌ ERROR: Failed to authenticate with Vault"
    exit 1
fi

echo "✅ Authenticated with Vault"
export VAULT_TOKEN

# Fetch database credentials
echo "📥 Fetching database credentials..."
export KC_DB_USERNAME=$(vault kv get -field=username secret/keycloak/database)
export KC_DB_PASSWORD=$(vault kv get -field=password secret/keycloak/database)

# Fetch admin credentials
echo "📥 Fetching admin credentials..."
export KEYCLOAK_ADMIN=$(vault kv get -field=username secret/keycloak/admin)
export KEYCLOAK_ADMIN_PASSWORD=$(vault kv get -field=password secret/keycloak/admin)

# Validate all credentials were fetched
if [ -z "$KC_DB_PASSWORD" ] || [ "$KC_DB_PASSWORD" = "null" ] || \
   [ -z "$KEYCLOAK_ADMIN_PASSWORD" ] || [ "$KEYCLOAK_ADMIN_PASSWORD" = "null" ]; then
    echo "❌ ERROR: Failed to fetch credentials from Vault"
    exit 1
fi

echo "✅ All credentials fetched successfully"
echo "  - Database user: $KC_DB_USERNAME"
echo "  - Admin user: $KEYCLOAK_ADMIN"
echo ""

# Fetch TLS certificates from Vault
echo "🔐 Fetching TLS certificates..."

CERTS_DIR="/opt/keycloak/certs"
KV_PATH="secret/data/keycloak/tls"
mkdir -p "$CERTS_DIR"

# Try to get existing certificate from KV store
EXISTING_CERT=$(vault kv get -format=json secret/keycloak/certificates 2>/dev/null || echo "")

if [ -n "$EXISTING_CERT" ] && echo "$EXISTING_CERT" | jq -e '.data.data.server_cert' > /dev/null 2>&1; then
    echo "  ✓ Using existing certificate from Vault KV"
    
    echo "$EXISTING_CERT" | jq -r '.data.data.server_cert' > "$CERTS_DIR/keycloak.crt"
    echo "$EXISTING_CERT" | jq -r '.data.data.server_key' > "$CERTS_DIR/keycloak.key"
    echo "$EXISTING_CERT" | jq -r '.data.data.ca_chain' > "$CERTS_DIR/ca.crt"
    
    chmod 644 "$CERTS_DIR/keycloak.crt"
    chmod 600 "$CERTS_DIR/keycloak.key"
    chmod 644 "$CERTS_DIR/ca.crt"
    
    # Enable HTTPS with certificate paths
    export KC_HTTPS_CERTIFICATE_FILE="$CERTS_DIR/keycloak.crt"
    export KC_HTTPS_CERTIFICATE_KEY_FILE="$CERTS_DIR/keycloak.key"
    
    # Use CA cert for Vault TLS verification
    if [ -f "$CERTS_DIR/ca.crt" ]; then
        export VAULT_CACERT="$CERTS_DIR/ca.crt"
        unset VAULT_SKIP_VERIFY
        echo "  ✓ Vault TLS verification enabled with CA cert"
    else
        export VAULT_SKIP_VERIFY=1
        echo "  ⚠ Vault TLS verification disabled (CA cert not found)"
    fi

    echo "  ✓ HTTPS enabled"
else
    echo "  ⚠ Certificate not found - HTTPS disabled"
    echo "  Add to secret/keycloak/certificates: server_cert, server_key, ca_chain"
    export VAULT_SKIP_VERIFY=1
fi

echo "========================================="
echo "Starting Keycloak..."
echo "========================================="

# Start Keycloak with the official entrypoint
exec /opt/keycloak/bin/kc.sh "$@"
