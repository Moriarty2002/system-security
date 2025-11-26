#!/bin/bash
# Script to configure LDAP secrets in Vault
# This should be run after Vault is initialized and unsealed

set -e

VAULT_ADDR="${VAULT_ADDR:-https://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-}"
VAULT_CONTAINER="shared_vault_server"

if [ -z "$VAULT_TOKEN" ]; then
    echo "❌ Error: VAULT_TOKEN environment variable is required"
    exit 1
fi

# Helper function to run vault commands in container
vault_exec() {
    docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
}

echo "🔐 Configuring LDAP secrets in Vault..."

# Store LDAP configuration in Vault
vault_exec kv put secret/mes_local_cloud/ldap \
    url="ldap://ldap-server:389" \
    bind_dn="cn=admin,dc=cloud,dc=mes" \
    bind_password="admin" \
    base_dn="dc=cloud,dc=mes"

echo "✅ LDAP configuration stored in Vault at secret/mes_local_cloud/ldap"

# Verify the secret was stored
echo ""
echo "📋 Verifying LDAP configuration:"
vault_exec kv get secret/mes_local_cloud/ldap

echo ""
echo "✅ LDAP secrets configuration complete!"
echo ""
echo "⚠️  SECURITY NOTE:"
echo "  - The LDAP admin password is set to 'admin' for development"
echo "  - In production, use a strong password and rotate regularly"
echo "  - Consider using LDAPS (LDAP over TLS) for encrypted connections"
echo "  - Restrict Vault access using policies (only backend should access LDAP secrets)"
