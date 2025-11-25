#!/bin/sh
set -e

# Fetch certificates from Vault on startup
VAULT_ADDR="${VAULT_ADDR:-https://shared_vault_server:8200}"
VAULT_ROLE_ID="${APACHE_VAULT_ROLE_ID}"
VAULT_SECRET_ID="${APACHE_VAULT_SECRET_ID}"
VAULT_AUTH_PATH="${APACHE_VAULT_AUTH_PATH:-approle-apache}"
PKI_ENGINE="${PKI_ENGINE:-pki_apache}"
PKI_ROLE="${PKI_ROLE:-apache-server}"
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

# First, try to get existing certificate from KV store
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
    echo "No existing certificate found, generating new one from PKI..."
    
    # Generate new certificate from PKI
    RESPONSE=$(wget --no-check-certificate -qO- \
      --method=POST \
      --header="X-Vault-Token: ${VAULT_TOKEN}" \
      --header="Content-Type: application/json" \
      --body-data='{"common_name":"localhost","alt_names":"localhost","ip_sans":"127.0.0.1","ttl":"720h"}' \
      "${VAULT_ADDR}/v1/${PKI_ENGINE}/issue/${PKI_ROLE}" 2>&1) || {
        echo "ERROR: Failed to generate certificate from Vault PKI"
        echo "Response: $RESPONSE"
        echo "Falling back to existing certificates on disk..."
        exec httpd-foreground
        exit 0
    }
    
    # Check if we got a valid response
    if echo "$RESPONSE" | grep -q '"certificate"'; then
        # Extract certificate and key
        CERT=$(echo "$RESPONSE" | jq -r '.data.certificate')
        KEY=$(echo "$RESPONSE" | jq -r '.data.private_key')
        CA_CHAIN=$(echo "$RESPONSE" | jq -r '.data.ca_chain[0]')
        
        # Save to disk for Apache
        echo "$CERT" > "${CERT_DIR}/user_certificate_signed.pem"
        echo "$KEY" > "${CERT_DIR}/user_priv_key.pem"
        
        chmod 644 "${CERT_DIR}/user_certificate_signed.pem"
        chmod 600 "${CERT_DIR}/user_priv_key.pem"
        
        echo "✓ Certificate generated from PKI"
        
        # Store in KV for reuse (certificate only persists in Vault)
        echo "Storing certificate in KV store for future use..."
        KV_DATA=$(jq -n \
          --arg cert "$CERT" \
          --arg key "$KEY" \
          --arg ca "$CA_CHAIN" \
          '{data: {server_cert: $cert, server_key: $key, ca_chain: $ca}}')
        
        wget --no-check-certificate -qO- \
          --method=POST \
          --header="X-Vault-Token: ${VAULT_TOKEN}" \
          --header="Content-Type: application/json" \
          --body-data="$KV_DATA" \
          "${VAULT_ADDR}/v1/${KV_PATH}" > /dev/null 2>&1 && \
          echo "✓ Certificate stored in KV store at ${KV_PATH}" || \
          echo "⚠ Warning: Could not store certificate in KV (will regenerate on next restart)"
    else
        echo "WARNING: No certificate in PKI response, using existing certificates on disk"
    fi
fi

echo "Starting Apache..."
# Start Apache
exec httpd-foreground
