# LDAP Integration Guide

## Overview

This project has been converted to use LDAP (Lightweight Directory Access Protocol) for centralized authentication and authorization. This provides enhanced security and better separation of concerns.

## Architecture Changes

### Before (Database Authentication)
- User credentials stored in PostgreSQL database
- Passwords hashed with Werkzeug
- Roles stored in database table

### After (LDAP Authentication)
- User credentials managed by OpenLDAP server
- Authentication delegated to LDAP (no password storage in app)
- Roles determined by LDAP group membership
- User metadata (quota, last login) stored in simplified database table

## Security Improvements

1. **Centralized Authentication**: Single source of truth for user credentials
2. **No Password Storage**: Application never stores password hashes
3. **Vault Integration**: LDAP bind credentials securely stored in Vault
4. **Role-Based Access**: Roles determined by LDAP group membership
5. **Audit Trail**: LDAP provides centralized authentication logging

## Components

### 1. LDAP Server (OpenLDAP)
- **Image**: `osixia/openldap:1.5.0`
- **Port**: 389 (LDAP), 636 (LDAPS)
- **Base DN**: `dc=cloud,dc=mes`
- **Admin DN**: `cn=admin,dc=cloud,dc=mes`

### 2. LDAP Directory Structure
```
dc=cloud,dc=mes
├── ou=users
│   ├── uid=admin
│   ├── uid=alice
│   └── uid=moderator
└── ou=groups
    ├── cn=admins (contains: admin)
    ├── cn=moderators (contains: moderator)
    └── cn=users (contains: alice)
```

### 3. Database Schema Changes
**New Table: `ldap_users`**
- Stores only user metadata (quota, email, display_name, last_login)
- No password_hash or role columns
- Roles determined dynamically from LDAP

**Old Table: `users`**
- Kept for backward compatibility
- Not used by LDAP authentication

### 4. Backend Changes
- New `ldap_client.py` module for LDAP operations
- Updated `auth.py` with `authenticate_ldap()` function
- LDAP configuration fetched from Vault
- JWT tokens include role from LDAP groups

## Setup Instructions

### 1. Initialize Vault with LDAP Credentials

```bash
cd vault-infrastructure
./scripts/init-vault.sh

# Set VAULT_TOKEN from the output
export VAULT_TOKEN="<root-token>"

# Configure LDAP secrets
cd ../homework/4_three_tier_app
chmod +x vault/scripts/setup-vault-ldap.sh
./vault/scripts/setup-vault-ldap.sh
```

### 2. Start the Application

```bash
docker-compose up -d
```

The LDAP server will automatically:
1. Initialize with base organizational units
2. Create default users (admin, alice, moderator)
3. Create groups for role-based access
4. Be ready for authentication

### 3. Test LDAP Authentication

```bash
# Test login with LDAP credentials
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password123"}'
```

## Default Users

| Username  | Password     | Role      | Group Membership |
|-----------|-------------|-----------|------------------|
| admin     | password123 | admin     | admins           |
| alice     | password123 | user      | users            |
| moderator | password123 | moderator | moderators       |

⚠️ **Change these passwords in production!**

## Role Mapping

Roles are determined by LDAP group membership with the following priority:

1. **admin**: Member of `cn=admins,ou=groups,dc=cloud,dc=mes`
2. **moderator**: Member of `cn=moderators,ou=groups,dc=cloud,dc=mes`
3. **user**: Member of `cn=users,ou=groups,dc=cloud,dc=mes` or default

## Configuration

### Vault Secret Path
`secret/mes_local_cloud/ldap`

**Required Fields:**
- `url`: LDAP server URL (e.g., `ldap://ldap-server:389`)
- `bind_dn`: DN to bind for user lookups (e.g., `cn=admin,dc=cloud,dc=mes`)
- `bind_password`: Password for bind DN
- `base_dn`: Base DN for searches (e.g., `dc=cloud,dc=mes`)

### Environment Variables
No additional environment variables needed - all configuration via Vault.

## LDAP Management

### Add a New User

1. Create LDIF file:
```ldif
dn: uid=newuser,ou=users,dc=cloud,dc=mes
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: newuser
cn: New User
sn: User
mail: newuser@example.org
uidNumber: 10004
gidNumber: 10004
homeDirectory: /home/newuser
loginShell: /bin/bash
userPassword: {SSHA}YourHashedPassword
```

2. Add to LDAP:
```bash
docker exec ldap_server ldapadd -x -D "cn=admin,dc=cloud,dc=mes" -w admin -f /path/to/newuser.ldif
```

3. Add to group:
```ldif
dn: cn=users,ou=groups,dc=cloud,dc=mes
changetype: modify
add: member
member: uid=newuser,ou=users,dc=cloud,dc=mes
```

### Change User Password

```bash
docker exec ldap_server ldappasswd -x -D "cn=admin,dc=cloud,dc=mes" -w admin \
  -s newpassword "uid=username,ou=users,dc=cloud,dc=mes"
```

### Search LDAP Directory

```bash
# List all users
docker exec ldap_server ldapsearch -x -H ldap://localhost \
  -b "ou=users,dc=cloud,dc=mes" -D "cn=admin,dc=cloud,dc=mes" -w admin

# List all groups
docker exec ldap_server ldapsearch -x -H ldap://localhost \
  -b "ou=groups,dc=cloud,dc=mes" -D "cn=admin,dc=cloud,dc=mes" -w admin
```

## Security Best Practices

### Production Deployment

1. **Use LDAPS (LDAP over TLS)**
   - Configure TLS certificates for LDAP server
   - Update LDAP URL to `ldaps://ldap-server:636`
   - Set `LDAP_TLS: "true"` in docker-compose.yaml

2. **Strong Passwords**
   - Change default LDAP admin password
   - Enforce strong password policies in LDAP
   - Use Vault's dynamic secrets for LDAP bind credentials

3. **Network Security**
   - Don't expose LDAP port (389) publicly
   - Use internal Docker network for backend-to-LDAP communication
   - Consider firewall rules for LDAP access

4. **Access Control**
   - Limit LDAP bind DN permissions (read-only for user lookups)
   - Use Vault policies to restrict LDAP secret access
   - Implement rate limiting on authentication endpoints

5. **Monitoring & Auditing**
   - Enable LDAP access logs
   - Monitor failed authentication attempts
   - Set up alerts for suspicious activity
   - Regular security audits of LDAP directory

6. **Backup & Recovery**
   - Regular backups of LDAP data volume
   - Document disaster recovery procedures
   - Test restoration process periodically

## Troubleshooting

### LDAP Connection Issues

```bash
# Test LDAP connectivity
docker exec backend ldapsearch -x -H ldap://ldap-server:389 \
  -b "dc=cloud,dc=mes" -D "cn=admin,dc=cloud,dc=mes" -w admin

# Check LDAP server logs
docker logs ldap_server
```

### Authentication Failures

1. Check LDAP user exists:
```bash
docker exec ldap_server ldapsearch -x -H ldap://localhost \
  -b "ou=users,dc=cloud,dc=mes" "(uid=username)" \
  -D "cn=admin,dc=cloud,dc=mes" -w admin
```

2. Verify group membership:
```bash
docker exec ldap_server ldapsearch -x -H ldap://localhost \
  -b "ou=groups,dc=cloud,dc=mes" "(member=uid=username,ou=users,dc=cloud,dc=mes)" \
  -D "cn=admin,dc=cloud,dc=mes" -w admin
```

3. Check backend logs:
```bash
docker logs flask_be
```

### Vault Configuration Issues

```bash
# Verify LDAP secret exists
vault kv get secret/mes_local_cloud/ldap

# Check backend has access to Vault
docker logs flask_be | grep -i vault
```

## Migration from Database Auth

Existing users in the `users` table are automatically migrated to `ldap_users` table on database initialization. However:

1. **Passwords are NOT migrated** - users must be recreated in LDAP
2. **Quotas are preserved** - copied to ldap_users table
3. **Roles are determined by LDAP groups** - not migrated from database

### Migration Steps

1. Export existing users from database
2. Create corresponding LDAP users
3. Assign LDAP users to appropriate groups
4. Test authentication for each user
5. Decommission old `users` table (optional)

## Benefits of LDAP Authentication

✅ **Security**
- No password storage in application
- Centralized credential management
- Better compliance with security standards

✅ **Scalability**
- Multiple applications can share LDAP directory
- Centralized user management
- Single sign-on (SSO) capability

✅ **Maintainability**
- Simplified application code
- No password management logic
- Standardized authentication protocol

✅ **Auditability**
- Centralized authentication logs
- Better visibility into access patterns
- Compliance with audit requirements

## References

- [OpenLDAP Documentation](https://www.openldap.org/doc/)
- [python-ldap Documentation](https://www.python-ldap.org/en/latest/)
- [RFC 4511 - LDAP Protocol](https://tools.ietf.org/html/rfc4511)
- [HashiCorp Vault LDAP Secrets Engine](https://www.vaultproject.io/docs/secrets/ldap)
