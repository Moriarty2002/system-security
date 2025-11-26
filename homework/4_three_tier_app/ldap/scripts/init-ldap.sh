#!/bin/bash
set -e

# Initialize LDAP directory with base structure and users
echo "Initializing LDAP directory..."

# Wait for LDAP server to be ready
sleep 5

# Add base organizational units
ldapadd -x -D "cn=admin,dc=cloud,dc=mes" -w admin -f /ldif/01-base.ldif || true

# Add users
ldapadd -x -D "cn=admin,dc=cloud,dc=mes" -w admin -f /ldif/02-users.ldif || true

# Add groups
ldapadd -x -D "cn=admin,dc=cloud,dc=mes" -w admin -f /ldif/03-groups.ldif || true

echo "LDAP directory initialized successfully"
