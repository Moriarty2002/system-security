#!/usr/bin/env bash
set -euo pipefail

# Minimal Keycloak setup script for the 'mes-local-cloud' realm and required clients/users/roles.
# Run this from the host where Docker is running. Requires Keycloak already up.
# Environment variables:
#  KEYCLOAK_ADMIN_USER - Keycloak master admin user (default: admin)
#  KEYCLOAK_ADMIN_PASSWORD - Keycloak master admin password
#  REALM_NAME - Realm to create (default: mes-local-cloud)

KEYCLOAK_ADMIN_USER=${KEYCLOAK_ADMIN_USER:-admin}
KEYCLOAK_ADMIN_PASSWORD=${KEYCLOAK_ADMIN_PASSWORD:-admin}
REALM_NAME=${REALM_NAME:-mes-local-cloud}

KC_CONTAINER=shared-keycloak-server
KCADM=/opt/keycloak/bin/kcadm.sh

echo "Logging into Keycloak ($KC_CONTAINER) as $KEYCLOAK_ADMIN_USER"
docker exec ${KC_CONTAINER} ${KCADM} config credentials --server http://localhost:8080 --realm master --user ${KEYCLOAK_ADMIN_USER} --password ${KEYCLOAK_ADMIN_PASSWORD}

echo "Creating realm: ${REALM_NAME}"
docker exec ${KC_CONTAINER} ${KCADM} create realms -s realm=${REALM_NAME} -s enabled=true -s displayName="MES Local Cloud"

echo "Creating realm roles: admin, moderator, user"
docker exec ${KC_CONTAINER} ${KCADM} create roles -r ${REALM_NAME} -s name=admin -s description="Administrator role" || true
docker exec ${KC_CONTAINER} ${KCADM} create roles -r ${REALM_NAME} -s name=moderator -s description="Moderator role" || true
docker exec ${KC_CONTAINER} ${KCADM} create roles -r ${REALM_NAME} -s name=user -s description="User role" || true

echo "Creating public client: mes-local-cloud-public"
docker exec ${KC_CONTAINER} ${KCADM} create clients -r ${REALM_NAME} \
  -s clientId=mes-local-cloud-public -s enabled=true -s publicClient=true -s standardFlowEnabled=true \
  -s directAccessGrantsEnabled=true -s 'redirectUris=["https://localhost/*","http://localhost/*"]' \
  -s 'webOrigins=["https://localhost","http://localhost"]' -s protocol=openid-connect || true

echo "Creating admin query client: mes-local-cloud-admin-query (confidential, service account)"
docker exec ${KC_CONTAINER} ${KCADM} get clients -r ${REALM_NAME} --fields clientId | jq -r '.[] | .clientId' | grep -q '^mes-local-cloud-admin-query$' || \
  docker exec ${KC_CONTAINER} ${KCADM} create clients -r ${REALM_NAME} -s clientId=mes-local-cloud-admin-query -s enabled=true -s publicClient=false -s serviceAccountsEnabled=true -s standardFlowEnabled=false -s directAccessGrantsEnabled=false -s fullScopeAllowed=false -s protocol=openid-connect

echo "Creating users: admin, alice, moderator and setting passwords"
docker exec ${KC_CONTAINER} ${KCADM} create users -r ${REALM_NAME} -s username=admin -s enabled=true || true
docker exec ${KC_CONTAINER} ${KCADM} create users -r ${REALM_NAME} -s username=alice -s enabled=true || true
docker exec ${KC_CONTAINER} ${KCADM} create users -r ${REALM_NAME} -s username=moderator -s enabled=true || true

echo "Setting passwords (admin/admin, alice/alice, moderator/moderator)"
docker exec ${KC_CONTAINER} ${KCADM} set-password -r ${REALM_NAME} --username admin --new-password admin || true
docker exec ${KC_CONTAINER} ${KCADM} set-password -r ${REALM_NAME} --username alice --new-password alice || true
docker exec ${KC_CONTAINER} ${KCADM} set-password -r ${REALM_NAME} --username moderator --new-password moderator || true

echo "Assigning roles to users"
# admin -> admin
docker exec ${KC_CONTAINER} ${KCADM} add-roles -r ${REALM_NAME} --uusername admin --rolename admin || true
# alice -> user
docker exec ${KC_CONTAINER} ${KCADM} add-roles -r ${REALM_NAME} --uusername alice --rolename user || true
# moderator -> moderator
docker exec ${KC_CONTAINER} ${KCADM} add-roles -r ${REALM_NAME} --uusername moderator --rolename moderator || true

echo "Configuring service account roles for mes-local-cloud-admin-query"
ADMIN_CLIENT_ID=$(docker exec ${KC_CONTAINER} ${KCADM} get clients -r ${REALM_NAME} --fields id,clientId | jq -r '.[] | select(.clientId=="mes-local-cloud-admin-query") | .id')
if [ -n "${ADMIN_CLIENT_ID}" ]; then
  SA_USER_ID=$(docker exec ${KC_CONTAINER} ${KCADM} get clients/${ADMIN_CLIENT_ID}/service-account-user -r ${REALM_NAME} | jq -r '.id')
  if [ -n "${SA_USER_ID}" ]; then
    echo "  Assigning realm-management roles to service account"
    docker exec ${KC_CONTAINER} ${KCADM} add-roles -r ${REALM_NAME} --uid ${SA_USER_ID} --cclientid realm-management --rolename view-users || true
    docker exec ${KC_CONTAINER} ${KCADM} add-roles -r ${REALM_NAME} --uid ${SA_USER_ID} --cclientid realm-management --rolename query-users || true
    docker exec ${KC_CONTAINER} ${KCADM} add-roles -r ${REALM_NAME} --uid ${SA_USER_ID} --cclientid realm-management --rolename query-groups || true
    echo "  Service account roles configured"
  fi
fi

echo "Keycloak setup completed."
