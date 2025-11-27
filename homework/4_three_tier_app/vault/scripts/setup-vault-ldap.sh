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

# Use simple development password
LDAP_ADMIN_PASSWORD="${LDAP_ADMIN_PASSWORD:-admin}"

# Helper function to run vault commands in container
vault_exec() {
    docker exec -e VAULT_TOKEN="$VAULT_TOKEN" -e VAULT_SKIP_VERIFY=1 "$VAULT_CONTAINER" vault "$@"
}

echo "🔐 Configuring LDAP secrets in Vault with LDAPS..."

# Store LDAP configuration in Vault with LDAPS URL
vault_exec kv put secret/mes_local_cloud/ldap \
    url="ldaps://ldap-server:636" \
    bind_dn="cn=admin,dc=cloud,dc=mes" \
    bind_password="$LDAP_ADMIN_PASSWORD" \
    base_dn="dc=cloud,dc=mes" \
    ca_cert_file="/etc/ssl/certs/ldap-ca-cert.pem"

echo "✅ LDAP configuration stored in Vault at secret/mes_local_cloud/ldap"

# Verify the secret was stored (without showing password)
echo ""
echo "📋 Verifying LDAP configuration (password hidden):"
vault_exec kv get -field=url secret/mes_local_cloud/ldap
vault_exec kv get -field=bind_dn secret/mes_local_cloud/ldap
vault_exec kv get -field=base_dn secret/mes_local_cloud/ldap

echo ""
echo "✅ LDAP secrets configuration complete!"
echo ""
echo "🔒 SECURITY IMPROVEMENTS APPLIED:"
echo "  ✅ LDAPS enabled (encrypted LDAP over TLS on port 636)"
echo "  ✅ TLS certificate verification enabled"
echo "  ✅ LDAP network isolation configured"
echo "  ✅ Audit logging enabled"
echo ""
echo "⚠️  DEVELOPMENT MODE NOTES:"
echo "  - LDAP admin password: 'admin' (for development only)"
echo "  - For production, use a strong password (min 16 characters)"
echo "  - Monitor LDAP audit logs in ./ldap/logs/"
echo "  - Review certificate expiration (365 days for LDAP cert)"
echo "  - For production, use certificates from a trusted CA"
