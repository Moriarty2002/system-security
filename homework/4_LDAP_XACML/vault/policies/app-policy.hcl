# Application Policy for Flask Backend
# This policy grants the Flask application read access to its secrets
# and write access to dynamic secrets/tokens if needed.

# Read application secrets (database credentials, JWT key, etc.)
path "secret/data/app/*" {
  capabilities = ["read", "list"]
}

# Read database credentials
path "secret/data/database/*" {
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
path "auth/approle/role/flask-app/role-id" {
  capabilities = ["read"]
}

# Write to get AppRole secret ID (for authentication)
path "auth/approle/role/flask-app/secret-id" {
  capabilities = ["update"]
}
