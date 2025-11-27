#!/bin/bash
# Setup LDAP PKI role and AppRole in Vault for certificate management

set -e

VAULT_TOKEN="${VAULT_TOKEN:-}"
VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
VAULT_CONTAINER="shared_vault_server"
PKI_ENGINE="${PKI_ENGINE:-pki_localhost}"

if [ -z "$VAULT_TOKEN" ]; then
    echo "❌ Error: VAULT_TOKEN environment variable is required"
    exit 1
fi

# Helper function to run vault commands in container
vault_exec() {
    docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
}

echo "🔐 Configuring LDAP PKI Role in Vault"
echo "======================================"
echo ""

# Check if PKI engine exists
echo "Checking PKI engine: ${PKI_ENGINE}..."
if vault_exec secrets list | grep -q "${PKI_ENGINE}/"; then
    echo "✅ PKI engine ${PKI_ENGINE} exists"
else
    echo "❌ PKI engine ${PKI_ENGINE} not found"
    echo "   Please ensure the PKI engine is enabled in Vault"
    echo "   Run: vault secrets enable -path=${PKI_ENGINE} pki"
    exit 1
fi

echo ""
echo "Creating PKI role for LDAP server..."

# Create PKI role for LDAP server certificates
vault_exec write ${PKI_ENGINE}/roles/ldap-server-localhost \
    allowed_domains="ldap-server,ldap,localhost" \
    allow_subdomains=false \
    allow_localhost=true \
    allow_ip_sans=true \
    allowed_ip_sans="127.0.0.1" \
    max_ttl="8760h" \
    ttl="8760h" \
    key_type="rsa" \
    key_bits=2048 \
    require_cn=true \
    allow_any_name=false

echo "✅ LDAP PKI role created: ${PKI_ENGINE}/roles/ldap-server-localhost"
echo ""

# Create AppRole for LDAP
echo "Creating AppRole for LDAP certificate management..."

# Enable AppRole auth method if not already enabled
vault_exec auth list | grep -q "approle-ldap/" || \
    vault_exec auth enable -path=approle-ldap approle

# Create policy for LDAP
POLICY_CONTENT="# Read/write LDAP certificates in KV
path \"secret/data/mes_local_cloud/certificates/ldap\" {
  capabilities = [\"create\", \"read\", \"update\"]
}

# Issue certificates from PKI
path \"${PKI_ENGINE}/issue/ldap-server-localhost\" {
  capabilities = [\"create\", \"update\"]
}

# Read CA certificate
path \"${PKI_ENGINE}/cert/ca\" {
  capabilities = [\"read\"]
}

# Token management
path \"auth/token/renew-self\" {
  capabilities = [\"update\"]
}

path \"auth/token/lookup-self\" {
  capabilities = [\"read\"]
}"

echo "$POLICY_CONTENT" | docker exec -i -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault policy write ldap-cert-policy -

echo "✅ LDAP certificate policy created"
echo ""

# Create AppRole
vault_exec write auth/approle-ldap/role/ldap-server \
    token_policies="ldap-cert-policy" \
    token_ttl=1h \
    token_max_ttl=4h \
    secret_id_ttl=0 \
    secret_id_num_uses=0

echo "✅ LDAP AppRole created: approle-ldap/role/ldap-server"
echo ""

# Get role ID
ROLE_ID=$(vault_exec read -field=role_id auth/approle-ldap/role/ldap-server/role-id)
echo "📋 LDAP AppRole Role ID:"
echo "   $ROLE_ID"
echo ""

# Generate secret ID
SECRET_ID=$(vault_exec write -field=secret_id -f auth/approle-ldap/role/ldap-server/secret-id)
echo "🔑 LDAP AppRole Secret ID (save this securely):"
echo "   $SECRET_ID"
echo ""

echo "======================================"
echo "✅ LDAP Vault Configuration Complete!"
echo "======================================"
echo ""
echo "📝 Add these to your .env file:"
echo ""
echo "LDAP_VAULT_ROLE_ID=$ROLE_ID"
echo "LDAP_VAULT_SECRET_ID=$SECRET_ID"
echo "LDAP_VAULT_AUTH_PATH=approle-ldap"
echo "LDAP_PKI_ROLE=ldap-server-localhost"
echo ""
echo "🔄 Next steps:"
echo "  1. Update .env file with the above values"
echo "  2. Rebuild LDAP container: docker-compose build ldap"
echo "  3. Restart LDAP: docker-compose up -d ldap"
echo ""
echo "🎯 LDAP will now fetch certificates from Vault automatically!"
echo "   - Certificates stored in: secret/mes_local_cloud/certificates/ldap"
echo "   - PKI role: ${PKI_ENGINE}/roles/ldap-server-localhost"
echo "   - Valid for: 1 year (8760h)"
echo ""
