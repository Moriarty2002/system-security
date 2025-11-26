# LDIF File Customization Guide

## Overview

LDIF (LDAP Data Interchange Format) files define the structure and content of your LDAP directory. This guide explains which parameters you can customize in the provided LDIF files.

## File: 01-base.ldif

### Organizational Units (OUs)

```ldif
dn: ou=users,dc=cloud,dc=mes
objectClass: organizationalUnit
ou: users
description: Container for user entries
```

**Customizable Parameters:**
- `dn`: Distinguished Name - defines the path in LDAP tree
  - `ou=users` - Can change to any name (e.g., `ou=people`, `ou=employees`)
  - `dc=cloud,dc=mes` - Must match your base DN
- `ou`: Must match the OU in the DN
- `description`: Free text describing the OU purpose

**Example - Rename to "people":**
```ldif
dn: ou=people,dc=cloud,dc=mes
objectClass: organizationalUnit
ou: people
description: All user accounts
```

## File: 02-users.ldif

### User Entries

```ldif
dn: uid=admin,ou=users,dc=cloud,dc=mes
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: admin
cn: Admin User
sn: User
givenName: Admin
mail: admin@example.org
uidNumber: 10001
gidNumber: 10001
homeDirectory: /home/admin
loginShell: /bin/bash
userPassword: {SSHA}ViDrgEyFgz3k9QTmMnHuR35ViBA7pEUL
description: Administrator
```

### Required Parameters (DO NOT REMOVE)

- `dn`: Distinguished Name - unique identifier
- `objectClass`: Defines what attributes this entry can have
  - `inetOrgPerson`: Basic person info (name, email)
  - `posixAccount`: Unix/Linux account info (UID, home directory)
  - `shadowAccount`: Password aging and expiration
- `uid`: Username for login **MUST BE UNIQUE**
- `cn`: Common Name - full name
- `sn`: Surname (last name)

### Customizable Parameters

#### Basic Identity
- **`uid`**: Login username
  - Example: `uid: jsmith`, `uid: john.smith`
  - ⚠️ Must be unique in the directory
  - ⚠️ Used for authentication

- **`cn`**: Full display name
  - Example: `cn: John Smith`, `cn: Smith, John`

- **`sn`**: Surname/last name
  - Example: `sn: Smith`, `sn: Doe`

- **`givenName`**: First name
  - Example: `givenName: John`, `givenName: Jane`

- **`mail`**: Email address
  - Example: `mail: john.smith@company.com`
  - Can be retrieved by application via LDAP

- **`description`**: User description or role
  - Example: `description: System Administrator`
  - Optional field

#### Unix/POSIX Attributes

- **`uidNumber`**: Numeric user ID
  - Example: `uidNumber: 10001`, `uidNumber: 10050`
  - ⚠️ Must be unique (typically start at 10000 for regular users)
  - Used for file system permissions

- **`gidNumber`**: Primary group ID
  - Example: `gidNumber: 10001`, `gidNumber: 100`
  - Can be same as uidNumber for personal groups
  - Or shared group ID for team groups

- **`homeDirectory`**: User's home directory path
  - Example: `homeDirectory: /home/jsmith`
  - Example: `homeDirectory: /users/john.smith`

- **`loginShell`**: Default shell
  - Example: `loginShell: /bin/bash`
  - Options: `/bin/bash`, `/bin/zsh`, `/bin/sh`, `/usr/bin/fish`

#### Password

- **`userPassword`**: Hashed password
  - Format: `{SSHA}base64encodedHash`
  - **Generate with:** `python3 -c "import hashlib, base64, os; salt=os.urandom(4); h=hashlib.sha1(b'yourpassword'); h.update(salt); print('{SSHA}' + base64.b64encode(h.digest()+salt).decode())"`
  - Or use `slappasswd -s yourpassword` inside LDAP container
  - ⚠️ Never store plain text passwords

### Optional Parameters You Can Add

```ldif
telephoneNumber: +1-555-1234          # Phone number
mobile: +1-555-5678                   # Mobile number
title: Senior Developer               # Job title
departmentNumber: Engineering         # Department
employeeNumber: EMP-12345             # Employee ID
street: 123 Main St                   # Street address
l: San Francisco                      # City (locality)
st: CA                                # State
postalCode: 94102                     # ZIP code
```

### Example: Adding a New User

```ldif
dn: uid=jdoe,ou=users,dc=cloud,dc=mes
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: jdoe
cn: John Doe
sn: Doe
givenName: John
mail: jdoe@example.org
telephoneNumber: +1-555-9999
title: Software Engineer
departmentNumber: Engineering
uidNumber: 10050
gidNumber: 10050
homeDirectory: /home/jdoe
loginShell: /bin/bash
userPassword: {SSHA}GenerateThisWithScript
description: Developer
```

## File: 03-groups.ldif

### Group Entries

```ldif
dn: cn=admins,ou=groups,dc=cloud,dc=mes
objectClass: groupOfNames
cn: admins
description: Administrators group
member: uid=admin,ou=users,dc=cloud,dc=mes
```

### Customizable Parameters

- **`dn`**: Group's distinguished name
  - `cn=admins` - Group name (e.g., `cn=developers`, `cn=managers`)
  - Must start with `cn=` for groups

- **`cn`**: Group name (must match DN)
  - Example: `cn: developers`, `cn: support-team`

- **`description`**: Group purpose
  - Example: `description: Development team members`

- **`member`**: List of group members (DN of users)
  - Format: `member: uid=username,ou=users,dc=cloud,dc=mes`
  - Can have multiple `member` lines
  - Example:
    ```ldif
    member: uid=alice,ou=users,dc=cloud,dc=mes
    member: uid=bob,ou=users,dc=cloud,dc=mes
    member: uid=charlie,ou=users,dc=cloud,dc=mes
    ```
  - ⚠️ At least one member is required for `groupOfNames`

### Role Mapping in Application

**For this application, groups map to roles:**
- `cn=admins` → **admin** role
- `cn=moderators` → **moderator** role  
- `cn=users` → **user** role

To change role names, update:
1. Group `cn` in LDIF
2. `ldap_client.py` - `get_user_role()` method

### Example: Adding a New Group

```ldif
dn: cn=developers,ou=groups,dc=cloud,dc=mes
objectClass: groupOfNames
cn: developers
description: Software development team
member: uid=alice,ou=users,dc=cloud,dc=mes
member: uid=bob,ou=users,dc=cloud,dc=mes
```

## Changing Base DN

If you want to use a different domain (e.g., `dc=mycompany,dc=com`):

1. **Update docker-compose.yaml:**
   ```yaml
   environment:
     LDAP_DOMAIN: "mycompany.com"
   ```

2. **Update all LDIF files:**
   - Replace `dc=cloud,dc=mes` with `dc=mycompany,dc=com`
   - Example: `dn: ou=users,dc=mycompany,dc=com`

3. **Update Vault LDAP configuration:**
   ```bash
   vault kv put secret/mes_local_cloud/ldap \
     base_dn="dc=mycompany,dc=com" \
     ...
   ```

4. **Update ldap_client.py if hardcoded anywhere**

## Password Generation Script

Save this as `generate_ldap_password.py`:

```python
#!/usr/bin/env python3
import hashlib
import base64
import os
import sys

def make_ssha_password(password):
    salt = os.urandom(4)
    h = hashlib.sha1(password.encode('utf-8'))
    h.update(salt)
    return "{SSHA}" + base64.b64encode(h.digest() + salt).decode('ascii')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./generate_ldap_password.py <password>")
        sys.exit(1)
    
    password = sys.argv[1]
    print(make_ssha_password(password))
```

**Usage:**
```bash
chmod +x generate_ldap_password.py
./generate_ldap_password.py mypassword
# Output: {SSHA}Xj8L1V5Y...
```

## Common Customization Scenarios

### 1. Add a New Regular User

```bash
cat > new_user.ldif << EOF
dn: uid=newuser,ou=users,dc=cloud,dc=mes
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: newuser
cn: New User
sn: User
givenName: New
mail: newuser@example.org
uidNumber: 10100
gidNumber: 10100
homeDirectory: /home/newuser
loginShell: /bin/bash
userPassword: {SSHA}GenerateThis
description: New team member
EOF

docker exec ldap_server ldapadd -x -D "cn=admin,dc=cloud,dc=mes" -w admin -f /path/to/new_user.ldif
```

### 2. Add User to Group

```bash
cat > add_to_group.ldif << EOF
dn: cn=users,ou=groups,dc=cloud,dc=mes
changetype: modify
add: member
member: uid=newuser,ou=users,dc=cloud,dc=mes
EOF

docker exec ldap_server ldapmodify -x -D "cn=admin,dc=cloud,dc=mes" -w admin -f /path/to/add_to_group.ldif
```

### 3. Create Team Group

```bash
cat > dev_team.ldif << EOF
dn: cn=developers,ou=groups,dc=cloud,dc=mes
objectClass: groupOfNames
cn: developers
description: Development team
member: uid=alice,ou=users,dc=cloud,dc=mes
member: uid=bob,ou=users,dc=cloud,dc=mes
EOF
```

## Validation

**Check for syntax errors:**
```bash
ldapsearch -x -H ldap://localhost -b "dc=cloud,dc=mes" -D "cn=admin,dc=cloud,dc=mes" -w admin
```

**Verify user exists:**
```bash
ldapsearch -x -H ldap://localhost -b "ou=users,dc=cloud,dc=mes" "(uid=username)"
```

**Verify group membership:**
```bash
ldapsearch -x -H ldap://localhost -b "ou=groups,dc=cloud,dc=mes" "(member=uid=username,ou=users,dc=cloud,dc=mes)"
```

## Best Practices

1. **uidNumber/gidNumber**: Start at 10000, increment for each user
2. **Passwords**: Always use SSHA hashed passwords, never plain text
3. **Email**: Use consistent domain for all users
4. **Backup**: Keep LDIF files version controlled
5. **Testing**: Test LDIF files on dev environment before production
6. **Unique IDs**: Ensure uid, uidNumber, and mail are unique
7. **Group Membership**: Every user should be in at least one group

## Troubleshooting

**Invalid DN error**: Check that base DN matches in all places  
**Constraint violation**: uidNumber or uid might not be unique  
**Invalid password**: Regenerate SSHA hash  
**Member not found**: Ensure user exists before adding to group

## References

- RFC 2849: LDIF Format Specification
- OpenLDAP Documentation: https://www.openldap.org/doc/
- LDAP Object Classes: https://ldapwiki.com/wiki/ObjectClass
