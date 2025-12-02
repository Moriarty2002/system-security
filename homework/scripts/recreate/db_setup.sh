#!/usr/bin/env bash
set -euo pipefail

# DB setup script: fetch Keycloak user IDs and insert minimal user_profiles rows in Postgres.
# Requires Keycloak admin credentials env vars or kcadm already configured in container.
#
# Environment variables (all have defaults):
#  KC_CONTAINER - Keycloak container name (default: shared-keycloak-server)
#  PG_CONTAINER - PostgreSQL container name (default: postgres_db)
#  REALM - Keycloak realm name (default: mes-local-cloud)
#  PG_USER - PostgreSQL user (default: admin)
#  PG_DB - PostgreSQL database (default: postgres_db)
#  DEFAULT_QUOTA - Default quota in bytes (default: 104857600 = 100MB)

KC_CONTAINER=${KC_CONTAINER:-shared-keycloak-server}
PG_CONTAINER=${PG_CONTAINER:-postgres_db}
REALM=${REALM:-mes-local-cloud}
PG_USER=${PG_USER:-admin}
PG_DB=${PG_DB:-postgres_db}
DEFAULT_QUOTA=${DEFAULT_QUOTA:-104857600}

echo "Fetching users from Keycloak realm '${REALM}' in container '${KC_CONTAINER}'"
ALL_USERS_JSON=$(docker exec ${KC_CONTAINER} /opt/keycloak/bin/kcadm.sh get users -r ${REALM} 2>&1)

if [ $? -ne 0 ]; then
  echo "Error: Failed to fetch users from Keycloak. Is kcadm.sh authenticated?"
  echo "Run: docker exec ${KC_CONTAINER} /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user <admin> --password <password>"
  exit 1
fi

if ! command -v jq &> /dev/null; then
  echo "Error: jq is required but not installed"
  exit 1
fi

echo "Inserting user_profiles for all Keycloak users (if missing)"
USER_COUNT=0
echo "$ALL_USERS_JSON" | jq -r '.[] | "\(.username) \(.id)"' | while read -r username id; do
  if [ -z "$username" ] || [ -z "$id" ]; then
    echo "  Warning: Skipping invalid user entry"
    continue
  fi
  
  echo "  - Ensuring profile for user '$username' (id=$id)"
  docker exec ${PG_CONTAINER} psql -U ${PG_USER} -d ${PG_DB} -c \
    "INSERT INTO user_profiles (keycloak_id, quota) VALUES ('${id}', ${DEFAULT_QUOTA}) ON CONFLICT (keycloak_id) DO NOTHING;" 2>&1 | grep -v "INSERT"
  
  USER_COUNT=$((USER_COUNT + 1))
done

echo ""
echo "✓ DB profiles created/ensured for realm '${REALM}'"
echo "  Total users processed: ${USER_COUNT}"
echo "  Default quota per user: ${DEFAULT_QUOTA} bytes ($(( DEFAULT_QUOTA / 1024 / 1024 ))MB)"
echo ""
