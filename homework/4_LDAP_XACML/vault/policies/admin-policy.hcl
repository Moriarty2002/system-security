# Admin Policy for Vault Management
# This policy grants full access for administrative tasks.
# Use this policy carefully and only for initial setup/maintenance.

# Full access to all secret paths
path "secret/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Manage auth methods
path "auth/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}

# Manage policies
path "sys/policies/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Manage AppRole
path "auth/approle/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# System backend
path "sys/*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}
