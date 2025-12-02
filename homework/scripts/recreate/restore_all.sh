#!/usr/bin/env bash
set -euo pipefail

# Orchestrator: runs all setup scripts in order.
# Ensure containers are running first (Vault unsealed, Keycloak healthy).
#
# Environment variables (all optional with defaults):
#  KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD - Keycloak admin credentials
#  REALM_NAME - Keycloak realm name (default: mes-local-cloud)
#  KC_CONTAINER - Keycloak container name (default: shared-keycloak-server)
#  VAULT_CONTAINER - Vault container name (default: shared_vault_server)
#  VAULT_TOKEN - Required for vault_setup.sh
#  CLIENT_SECRET_ADMIN - Required for vault_setup.sh (mes-local-cloud-admin-query client secret)
#  PG_CONTAINER - PostgreSQL container name (default: postgres_db)
#  PG_USER - PostgreSQL user (default: admin)
#  PG_DB - PostgreSQL database (default: postgres_db)
#  DEFAULT_QUOTA - User quota in bytes (default: 104857600)

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  System Restoration Orchestrator"
echo "=========================================="
echo ""
echo "Prerequisites check:"
echo "  - Ensure Vault container is running and unsealed"
echo "  - Ensure Keycloak container is running and healthy"
echo "  - Ensure PostgreSQL container is running"
echo "  - Set VAULT_TOKEN environment variable"
echo "  - Set CLIENT_SECRET_ADMIN environment variable"
echo ""

if [ -z "${VAULT_TOKEN:-}" ]; then
  echo "Error: VAULT_TOKEN not set"
  echo "Export it first: export VAULT_TOKEN=hvs...."
  exit 1
fi

if [ -z "${CLIENT_SECRET_ADMIN:-}" ]; then
  echo "Warning: CLIENT_SECRET_ADMIN not set"
  echo "You must set it after Step 1 completes before continuing to Step 2"
  echo "Get it with: docker exec shared-keycloak-server /opt/keycloak/bin/kcadm.sh get clients/<uuid>/client-secret -r <realm>"
  echo ""
  read -p "Continue with Step 1 only? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
  PARTIAL_RUN=true
fi

echo "========== Step 1: Keycloak Setup =========="
echo "Creating realm, roles, clients, users..."
${DIR}/keycloak_setup.sh

if [ "${PARTIAL_RUN:-false}" = "true" ]; then
  echo ""
  echo "=========================================="
  echo "  Step 1 Complete - ACTION REQUIRED"
  echo "=========================================="
  echo ""
  echo "Next steps:"
  echo "1. Get the mes-local-cloud-admin-query client secret:"
  REALM=${REALM_NAME:-mes-local-cloud}
  KC=${KC_CONTAINER:-shared-keycloak-server}
  echo "   CLIENT_ID_UUID=\$(docker exec ${KC} /opt/keycloak/bin/kcadm.sh get clients -r ${REALM} -q clientId=mes-local-cloud-admin-query --fields id --format csv --noquotes)"
  echo "   export CLIENT_SECRET_ADMIN=\$(docker exec ${KC} /opt/keycloak/bin/kcadm.sh get clients/\${CLIENT_ID_UUID}/client-secret -r ${REALM} | jq -r '.value')"
  echo ""
  echo "2. Run remaining steps:"
  echo "   bash vault_setup.sh"
  echo "   bash db_setup.sh"
  exit 0
fi

echo ""
echo "Waiting for Keycloak to stabilize..."
sleep 5

echo "========== Step 2: Vault Setup =========="
echo "Writing Keycloak client configuration to Vault..."
${DIR}/vault_setup.sh

echo ""
echo "Waiting for Vault to finalize writes..."
sleep 2

echo "========== Step 3: DB Setup =========="
echo "Creating user_profiles in PostgreSQL..."
${DIR}/db_setup.sh

echo ""
echo "=========================================="
echo "  ALL SETUP COMPLETE"
echo "=========================================="
echo ""
echo "System restoration summary:"
echo "  ✓ Keycloak realm '${REALM_NAME:-mes-local-cloud}' configured"
echo "  ✓ Vault secrets written to secret/keycloak/client"
echo "  ✓ User profiles created in PostgreSQL"
echo ""
echo "Next steps:"
echo "1. Verify Keycloak configuration:"
echo "   curl -k https://localhost:8443/realms/${REALM_NAME:-mes-local-cloud}/.well-known/openid-configuration"
echo ""
echo "2. Test authentication:"
echo "   curl -k -X POST https://localhost:8443/realms/${REALM_NAME:-mes-local-cloud}/protocol/openid-connect/token \\"
echo "     -d 'client_id=mes-local-cloud-public&grant_type=password&username=alice&password=alice'"
echo ""
echo "3. Start the application stack (if not already running)"
echo ""
