#!/usr/bin/env bash
set -euo pipefail

# Vault secrets writer for the app. Requires VAULT_TOKEN set in environment.
# This script stores the Keycloak client configuration used by the frontend/backend.
#
# Environment variables (all have defaults except VAULT_TOKEN and CLIENT_SECRET_ADMIN):
#  VAULT_TOKEN - Required, Vault root or admin token
#  VAULT_CONTAINER - Vault container name (default: shared_vault_server)
#  CLIENT_ID - Frontend client ID (default: mes-local-cloud-public)
#  CLIENT_SECRET - Frontend client secret (default: generated value)
#  CLIENT_ID_ADMIN - Backend admin client ID (default: mes-local-cloud-admin-query)
#  CLIENT_SECRET_ADMIN - Backend admin client secret (REQUIRED, get from Keycloak)
#  REALM - Keycloak realm name (default: mes-local-cloud)
#  SERVER_URL - Keycloak internal URL (default: https://shared-keycloak-server:8443)
#  SERVER_URL_EXTERNAL - Keycloak external URL (default: https://localhost:8443)

VAULT_CONTAINER=${VAULT_CONTAINER:-shared_vault_server}
VAULT_PATH=secret/keycloak/client

if [ -z "${VAULT_TOKEN:-}" ]; then
  echo "Error: VAULT_TOKEN must be set in the environment"
  exit 1
fi

if [ -z "${CLIENT_SECRET_ADMIN:-}" ]; then
  echo "Error: CLIENT_SECRET_ADMIN must be set"
  echo "Get it with: docker exec shared-keycloak-server /opt/keycloak/bin/kcadm.sh get clients/<client-uuid>/client-secret -r <realm>"
  exit 1
fi

CLIENT_ID=${CLIENT_ID:-mes-local-cloud-public}
CLIENT_SECRET=${CLIENT_SECRET:-iNHzaKf+d01VCBmSSq9G4tz/3PzOopTZE9FuAlZj4Zk=}
CLIENT_ID_ADMIN=${CLIENT_ID_ADMIN:-mes-local-cloud-admin-query}
REALM=${REALM:-mes-local-cloud}
SERVER_URL=${SERVER_URL:-https://shared-keycloak-server:8443}
SERVER_URL_EXTERNAL=${SERVER_URL_EXTERNAL:-https://localhost:8443}

echo "Writing Keycloak client config to Vault at ${VAULT_PATH}"
echo "  Realm: ${REALM}"
echo "  Client ID: ${CLIENT_ID}"
echo "  Admin Client ID: ${CLIENT_ID_ADMIN}"

docker exec -e VAULT_TOKEN=${VAULT_TOKEN} ${VAULT_CONTAINER} vault kv put ${VAULT_PATH} \
  client_id=${CLIENT_ID} \
  client_secret="${CLIENT_SECRET}" \
  client_id_admin=${CLIENT_ID_ADMIN} \
  client_secret_admin="${CLIENT_SECRET_ADMIN}" \
  realm=${REALM} \
  server_url=${SERVER_URL} \
  server_url_external=${SERVER_URL_EXTERNAL}

echo "✓ Vault secrets written successfully"
echo ""
echo "Optional: Add CA certificate for Flask backend SSL verification:"
echo "  docker exec -e VAULT_TOKEN=\$VAULT_TOKEN ${VAULT_CONTAINER} \\"
echo "    vault kv patch secret/mes_local_cloud/app/flask \\"
echo "    CA_chain=\"\$(cat ca.pem)\""

echo ""
