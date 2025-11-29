# Keycloak Policy
# This policy allows read access to Keycloak secrets

# Allow reading Keycloak database credentials
path "secret/data/keycloak/database" {
  capabilities = ["read"]
}

# Allow reading Keycloak admin credentials
path "secret/data/keycloak/admin" {
  capabilities = ["read"]
}

# Allow reading TLS certificates
path "secret/data/keycloak/certificates" {
  capabilities = ["read"]
}

# Allow listing secrets (optional, for debugging)
path "secret/metadata/keycloak/*" {
  capabilities = ["list"]
}
