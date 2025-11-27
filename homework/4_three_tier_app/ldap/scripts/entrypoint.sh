#!/bin/bash
set -e

# Fetch certificates from Vault on startup for LDAP server
VAULT_ADDR="${VAULT_ADDR}"
VAULT_ROLE_ID="${LDAP_VAULT_ROLE_ID}"
VAULT_SECRET_ID="${LDAP_VAULT_SECRET_ID}"
VAULT_AUTH_PATH="${LDAP_VAULT_AUTH_PATH}"
PKI_ENGINE="${PKI_ENGINE}"
PKI_ROLE="${PKI_ROLE}"

CERT_DIR="/container/service/slapd/assets/certs"
KV_PATH="secret/data/mes_local_cloud/certificates/ldap"

echo "🔐 LDAP Certificate Management via Vault"
echo "========================================"

# Validate required Vault configuration
if [ -z "$VAULT_ADDR" ] || [ -z "$VAULT_ROLE_ID" ] || [ -z "$VAULT_SECRET_ID" ] || [ -z "$VAULT_AUTH_PATH" ] || [ -z "$PKI_ENGINE" ] || [ -z "$PKI_ROLE" ]; then
    echo "❌ ERROR: Missing required Vault configuration:"
    [ -z "$VAULT_ADDR" ] && echo "   - VAULT_ADDR"
    [ -z "$VAULT_ROLE_ID" ] && echo "   - LDAP_VAULT_ROLE_ID"
    [ -z "$VAULT_SECRET_ID" ] && echo "   - LDAP_VAULT_SECRET_ID"
    [ -z "$VAULT_AUTH_PATH" ] && echo "   - LDAP_VAULT_AUTH_PATH"
    [ -z "$PKI_ENGINE" ] && echo "   - PKI_ENGINE"
    [ -z "$PKI_ROLE" ] && echo "   - PKI_ROLE (LDAP_PKI_ROLE)"
    echo ""
    echo "All LDAP certificates must come from Vault."
    echo "Please configure Vault and set the required environment variables."
    exit 1
fi

echo "Authenticating with Vault using AppRole..."

# Authenticate with AppRole to get a token
AUTH_RESPONSE=$(wget --no-check-certificate -qO- \
  --method=POST \
  --header="Content-Type: application/json" \
  --body-data="{\"role_id\":\"${VAULT_ROLE_ID}\",\"secret_id\":\"${VAULT_SECRET_ID}\"}" \
  "${VAULT_ADDR}/v1/auth/${VAULT_AUTH_PATH}/login" 2>&1) || {
    echo "❌ Failed to authenticate with Vault AppRole"
    echo "   Falling back to local certificates..."
    exec /container/tool/run
}

# Extract token from response
VAULT_TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.auth.client_token' 2>/dev/null)

if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
    echo "❌ Failed to obtain Vault token"
    echo "   Falling back to local certificates..."
    exec /container/tool/run
fi

echo "✅ Successfully authenticated with Vault"
echo ""

# Try to get existing certificate from KV store first
echo "Checking for existing LDAP certificate in Vault KV..."
EXISTING_CERT=$(wget --no-check-certificate -qO- \
  --header "X-Vault-Token: ${VAULT_TOKEN}" \
  "${VAULT_ADDR}/v1/${KV_PATH}" 2>&1 || echo "")

if echo "$EXISTING_CERT" | grep -q '"ldap_cert"'; then
    echo "✅ Found existing certificate in KV store"
    
    # Extract certificate, key, and CA from KV store
    echo "$EXISTING_CERT" | jq -r '.data.data.ldap_cert' > "${CERT_DIR}/ldap-cert.pem"
    echo "$EXISTING_CERT" | jq -r '.data.data.ldap_key' > "${CERT_DIR}/ldap-key.pem"
    echo "$EXISTING_CERT" | jq -r '.data.data.ca_cert' > "${CERT_DIR}/ca-cert.pem"
    
    # DH params (optional, can be local or from Vault)
    if echo "$EXISTING_CERT" | jq -e '.data.data.dhparam' > /dev/null 2>&1; then
        echo "$EXISTING_CERT" | jq -r '.data.data.dhparam' > "${CERT_DIR}/dhparam.pem"
    elif [ ! -f "${CERT_DIR}/dhparam.pem" ]; then
        echo "Generating DH parameters (this may take a moment)..."
        openssl dhparam -out "${CERT_DIR}/dhparam.pem" 2048 2>/dev/null || echo "⚠️  Could not generate DH params"
    fi
    
    # Set proper permissions
    chmod 644 "${CERT_DIR}/ldap-cert.pem" "${CERT_DIR}/ca-cert.pem"
    chmod 600 "${CERT_DIR}/ldap-key.pem"
    [ -f "${CERT_DIR}/dhparam.pem" ] && chmod 644 "${CERT_DIR}/dhparam.pem"
    
    echo "✅ Certificate retrieved from KV store"
else
    echo "No existing certificate found, generating new one from PKI..."
    
    # Generate new certificate from Vault PKI
    RESPONSE=$(wget --no-check-certificate -qO- \
      --method=POST \
      --header="X-Vault-Token: ${VAULT_TOKEN}" \
      --header="Content-Type: application/json" \
      --body-data='{"common_name":"ldap-server","alt_names":"ldap-server,ldap,localhost","ip_sans":"127.0.0.1","ttl":"8760h"}' \
      "${VAULT_ADDR}/v1/${PKI_ENGINE}/issue/${PKI_ROLE}" 2>&1) || {
        echo "❌ Failed to generate certificate from Vault PKI"
        echo "   Falling back to local certificates..."
        exec /container/tool/run
    }
    
    # Check if we got a valid response
    if echo "$RESPONSE" | jq -e '.data.certificate' > /dev/null 2>&1; then
        # Extract certificate, key, and CA chain
        CERT=$(echo "$RESPONSE" | jq -r '.data.certificate')
        KEY=$(echo "$RESPONSE" | jq -r '.data.private_key')
        CA_CHAIN=$(echo "$RESPONSE" | jq -r '.data.ca_chain[0]' 2>/dev/null || echo "$RESPONSE" | jq -r '.data.issuing_ca')
        
        # Save to disk for LDAP
        echo "$CERT" > "${CERT_DIR}/ldap-cert.pem"
        echo "$KEY" > "${CERT_DIR}/ldap-key.pem"
        echo "$CA_CHAIN" > "${CERT_DIR}/ca-cert.pem"
        
        # Generate DH parameters if not exists
        if [ ! -f "${CERT_DIR}/dhparam.pem" ]; then
            echo "Generating DH parameters..."
            openssl dhparam -out "${CERT_DIR}/dhparam.pem" 2048 2>/dev/null || echo "⚠️  Could not generate DH params"
        fi
        
        # Set proper permissions
        chmod 644 "${CERT_DIR}/ldap-cert.pem" "${CERT_DIR}/ca-cert.pem"
        chmod 600 "${CERT_DIR}/ldap-key.pem"
        [ -f "${CERT_DIR}/dhparam.pem" ] && chmod 644 "${CERT_DIR}/dhparam.pem"
        
        echo "✅ Certificate generated from PKI"
        
        # Store in KV for reuse
        echo "Storing certificate in KV store for future use..."
        DHPARAM_CONTENT=""
        if [ -f "${CERT_DIR}/dhparam.pem" ]; then
            DHPARAM_CONTENT=$(cat "${CERT_DIR}/dhparam.pem")
        fi
        
        KV_DATA=$(jq -n \
          --arg cert "$CERT" \
          --arg key "$KEY" \
          --arg ca "$CA_CHAIN" \
          --arg dh "$DHPARAM_CONTENT" \
          '{data: {ldap_cert: $cert, ldap_key: $key, ca_cert: $ca, dhparam: $dh}}')
        
        wget --no-check-certificate -qO- \
          --method=POST \
          --header="X-Vault-Token: ${VAULT_TOKEN}" \
          --header="Content-Type: application/json" \
          --body-data="$KV_DATA" \
          "${VAULT_ADDR}/v1/${KV_PATH}" > /dev/null 2>&1 && \
          echo "✅ Certificate stored in KV store at ${KV_PATH}" || \
          echo "⚠️  Could not store certificate in KV (will regenerate on next restart)"
    else
        echo "❌ No certificate in PKI response"
        echo "   Falling back to local certificates..."
        exec /container/tool/run
    fi
fi

echo ""
echo "📋 Certificate Details:"
echo "   Certificate: ${CERT_DIR}/ldap-cert.pem"
echo "   Private Key: ${CERT_DIR}/ldap-key.pem"
echo "   CA Chain:    ${CERT_DIR}/ca-cert.pem"
[ -f "${CERT_DIR}/dhparam.pem" ] && echo "   DH Params:   ${CERT_DIR}/dhparam.pem"
echo ""
echo "🚀 Starting OpenLDAP server with Vault-managed certificates..."
echo ""

# Start LDAP
exec /container/tool/run
