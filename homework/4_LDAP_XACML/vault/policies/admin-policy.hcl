# Admin Policy for 4_LDAP_XACML Vault Management
# This policy grants administrative access for managing this application's
# secrets in the shared Vault infrastructure.
#
# Use this policy carefully and only for initial setup/maintenance.

# Full access to application's secret paths
path "secret/data/4_ldap_xacml/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/4_ldap_xacml/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Manage application-specific AppRole
path "auth/approle/role/4_ldap_xacml-*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
