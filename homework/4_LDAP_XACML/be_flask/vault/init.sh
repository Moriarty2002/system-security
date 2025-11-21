#!/bin/sh
set -eu

# init.sh - run inside a container that has the Vault CLI (the official vault image)
# This script waits for Vault to be available, logs in using the provided token,
# enables kv v2 at path `secret`, writes a test secret under `secret/flask`,
# creates a read-only policy for that path, creates an AppRole, and saves
# role_id/secret_id into mounted files under /vault.

VAULT_ADDR=${VAULT_ADDR:-http://vault:8200}
VAULT_TOKEN=${VAULT_TOKEN:-root}

export VAULT_ADDR

echo "Waiting for Vault at $VAULT_ADDR..."
until /bin/sh -c "nc -z $(echo $VAULT_ADDR | sed -e 's~http[s]*://~~' -e 's/:.*//') 8200" >/dev/null 2>&1; do
  sleep 1
done

echo "Logging into Vault with token (dev)..."
vault login ${VAULT_TOKEN} || true

# Enable KV v2 at path secret (idempotent)
vault secrets enable -path=secret -version=2 kv || true

# Write demo secret for Flask including default user passwords for local testing
# In production, do NOT store plaintext passwords in Vault like this; this is
# for local/dev convenience only.
vault kv put secret/flask \
  SECRET_KEY=dev-secret-key \
  DATABASE_URL=postgresql://admin:password123@db:5432/postgres_db \
  ADMIN_PASSWORD=admin \
  ALICE_PASSWORD=alice \
  MOD_PASSWORD=moderator || true

# Create a policy that allows read to secret/data/flask
cat > /vault/flask-policy.hcl <<'HCL'
path "secret/data/flask" {
  capabilities = ["read"]
}
HCL

vault policy write flask-policy /vault/flask-policy.hcl || true

# Create or ensure an AppRole exists and get role_id and secret_id
vault write auth/approle/role/flask-role token_ttl=1h token_max_ttl=4h policies=flask-policy || true

# Read role_id and secret_id and save them to files under /vault
vault read -format=json auth/approle/role/flask-role/role-id > /vault/role_id.json || true
vault write -format=json -f auth/approle/role/flask-role/secret-id > /vault/secret_id.json || true

# Print summary for convenience
echo "Vault initialization complete. Role ID and Secret ID are in /vault/role_id.json and /vault/secret_id.json"

exit 0
