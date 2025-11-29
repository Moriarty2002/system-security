# PKI Policy for Apache frontend and related services
# Grants minimal permissions to issue certificates from the PKI engine
# and to read certificate data stored in the KV namespace for Apache.

# Allow issuing certificates from the shared PKI engine (pki_localhost)
path "pki_localhost/issue/*" {
  capabilities = ["create", "update", "read"]
}

# Allow reading the CA certificate
path "pki_localhost/cert/ca" {
  capabilities = ["read"]
}

# Allow the role to read stored certificate blobs for Apache
path "secret/data/mes_local_cloud/certificates/*" {
  capabilities = ["read", "list"]
}

# Allow token lookup/renew for the role's token
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}
