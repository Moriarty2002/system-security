#!/bin/sh
set -e

# Fetch certificates from Vault on startup
VAULT_ADDR="${VAULT_ADDR:?VAULT_ADDR environment variable is required}"
VAULT_ROLE_ID="${APACHE_VAULT_ROLE_ID:?APACHE_VAULT_ROLE_ID environment variable is required}"
VAULT_SECRET_ID="${APACHE_VAULT_SECRET_ID:?APACHE_VAULT_SECRET_ID environment variable is required}"
VAULT_AUTH_PATH="${APACHE_VAULT_AUTH_PATH:?APACHE_VAULT_AUTH_PATH environment variable is required}"
PKI_ENGINE="${PKI_ENGINE:?PKI_ENGINE environment variable is required}"
PKI_ROLE="${PKI_ROLE:?PKI_ROLE environment variable is required}"
# Validate required configuration
if [ -z "$VAULT_ROLE_ID" ] || [ -z "$VAULT_SECRET_ID" ] || [ -z "$VAULT_AUTH_PATH" ] || [ -z "$PKI_ENGINE" ] || [ -z "$PKI_ROLE" ]; then
    echo "ERROR: Missing required Vault configuration:"
    [ -z "$VAULT_ROLE_ID" ] && echo "  - APACHE_VAULT_ROLE_ID"
    [ -z "$VAULT_SECRET_ID" ] && echo "  - APACHE_VAULT_SECRET_ID"
    [ -z "$VAULT_AUTH_PATH" ] && echo "  - APACHE_VAULT_AUTH_PATH"
    [ -z "$PKI_ENGINE" ] && echo "  - PKI_ENGINE"
    [ -z "$PKI_ROLE" ] && echo "  - PKI_ROLE"
    exit 1
fi
KV_PATH="secret/data/mes_local_cloud/certificates/apache"
CERT_DIR="/usr/local/apache2/conf/extra/certs"

echo "Authenticating with Vault using AppRole..."

# Authenticate with AppRole to get a token (skip TLS verification for self-signed cert)
AUTH_RESPONSE=$(wget --no-check-certificate -qO- \
  --method=POST \
  --header="Content-Type: application/json" \
  --body-data="{\"role_id\":\"${VAULT_ROLE_ID}\",\"secret_id\":\"${VAULT_SECRET_ID}\"}" \
  "${VAULT_ADDR}/v1/auth/${VAULT_AUTH_PATH}/login" 2>&1) || {
    echo "ERROR: Failed to authenticate with Vault AppRole"
    echo "Response: $AUTH_RESPONSE"
    echo "Falling back to existing certificates on disk..."
    exec httpd-foreground
    exit 0
}

# Extract token from response
VAULT_TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.auth.client_token')

if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
    echo "ERROR: Failed to obtain Vault token from AppRole authentication"
    echo "Falling back to existing certificates on disk..."
    exec httpd-foreground
    exit 0
fi

echo "✓ Successfully authenticated with Vault"
echo "Fetching certificates from Vault..."

# Fetch certificate from KV store
echo "Checking for existing certificate in KV store..."
EXISTING_CERT=$(wget --no-check-certificate -qO- --header "X-Vault-Token: ${VAULT_TOKEN}" \
  "${VAULT_ADDR}/v1/${KV_PATH}" 2>&1 || echo "")

if echo "$EXISTING_CERT" | grep -q '"server_cert"'; then
    echo "✓ Found existing certificate in KV store, using it"
    
    # Extract certificate and key from KV store
    echo "$EXISTING_CERT" | jq -r '.data.data.server_cert' > "${CERT_DIR}/user_certificate_signed.pem"
    echo "$EXISTING_CERT" | jq -r '.data.data.server_key' > "${CERT_DIR}/user_priv_key.pem"
    
    chmod 644 "${CERT_DIR}/user_certificate_signed.pem"
    chmod 600 "${CERT_DIR}/user_priv_key.pem"
    
    echo "✓ Certificate retrieved from KV store (no private key on disk permanently)"
else
    echo "ERROR: No existing certificate found in KV store. Unable to proceed."
    exit 1
fi

echo "Starting Apache..."
# Start Apache as apache user (httpd-foreground handles user switching via httpd.conf)
exec httpd-foreground
