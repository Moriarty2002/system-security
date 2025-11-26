# Application Policy for 4_three_tier_app Flask Backend
# This policy grants the Flask application read access to its secrets
# stored in the shared Vault infrastructure.
#
# Secrets are namespaced under: secret/mes_local_cloud/

# Read application secrets (database credentials, JWT key, etc.)
path "secret/data/mes_local_cloud/app/*" {
  capabilities = ["read", "list"]
}

# Read database credentials
path "secret/data/mes_local_cloud/database/*" {
  capabilities = ["read"]
}

# Read MinIO object storage credentials
path "secret/data/mes_local_cloud/minio" {
  capabilities = ["read"]
}

# Allow the app to renew its own token
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow the app to lookup its own token
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

# Read AppRole role ID (for authentication)
path "auth/approle/role/mes_local_cloud-flask-app/role-id" {
  capabilities = ["read"]
}

# Write to get AppRole secret ID (for authentication)
path "auth/approle/role/mes_local_cloud-flask-app/secret-id" {
  capabilities = ["update"]
}
