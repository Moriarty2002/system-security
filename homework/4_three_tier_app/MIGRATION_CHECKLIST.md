# LDAP Migration Checklist

## Pre-Migration

- [ ] **Backup existing database**
  ```bash
  docker exec postgres_db pg_dump -U postgres mes_local_cloud > backup_pre_ldap.sql
  ```

- [ ] **Document existing users and their roles**
  ```bash
  docker exec postgres_db psql -U postgres mes_local_cloud -c "SELECT username, role, quota FROM users;"
  ```

- [ ] **Ensure Vault infrastructure is running**
  ```bash
  docker ps | grep shared_vault_server
  ```

- [ ] **Have Vault root token available**
  ```bash
  export VAULT_TOKEN=<root-token>
  ```

## Migration Steps

### 1. Configure LDAP Secrets in Vault

- [ ] Run LDAP setup script
  ```bash
  cd homework/4_three_tier_app
  chmod +x vault/scripts/setup-vault-ldap.sh
  ./vault/scripts/setup-vault-ldap.sh
  ```

- [ ] Verify LDAP secrets stored
  ```bash
  vault kv get secret/mes_local_cloud/ldap
  ```

### 2. Create LDAP Users

For each existing database user, create corresponding LDAP user:

- [ ] **Admin user** (default: already exists in 02-users.ldif)
  - Username: admin
  - Password: password123 (change this!)
  - Group: admins

- [ ] **Alice user** (default: already exists in 02-users.ldif)
  - Username: alice
  - Password: password123 (change this!)
  - Group: users

- [ ] **Moderator user** (default: already exists in 02-users.ldif)
  - Username: moderator
  - Password: password123 (change this!)
  - Group: moderators

**For additional users:**
```bash
# Create LDIF file for new user
cat > newuser.ldif << EOF
dn: uid=newuser,ou=users,dc=cloud,dc=mes
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: newuser
cn: New User
sn: User
mail: newuser@example.org
uidNumber: 10005
gidNumber: 10005
homeDirectory: /home/newuser
loginShell: /bin/bash
userPassword: {SSHA}GenerateWithSlappasswd
EOF

# Add to LDAP
docker exec ldap_server ldapadd -x -D "cn=admin,dc=cloud,dc=mes" \
  -w admin -f /path/to/newuser.ldif

# Add to appropriate group
cat > add_to_group.ldif << EOF
dn: cn=users,ou=groups,dc=cloud,dc=mes
changetype: modify
add: member
member: uid=newuser,ou=users,dc=cloud,dc=mes
EOF

docker exec ldap_server ldapmodify -x -D "cn=admin,dc=cloud,dc=mes" \
  -w admin -f /path/to/add_to_group.ldif
```

### 3. Update Application Configuration

- [ ] Ensure AppRole credentials are set in .env
  ```bash
  # Check vault/scripts/approle-credentials.txt
  # Add VAULT_ROLE_ID and VAULT_SECRET_ID to .env
  ```

- [ ] Review docker-compose.yaml changes
  - [ ] LDAP service added
  - [ ] Backend depends on LDAP
  - [ ] Volumes for LDAP data

- [ ] Review Dockerfile changes
  - [ ] python-ldap system dependencies added

### 4. Start Services

- [ ] Stop existing services
  ```bash
  docker-compose down
  ```

- [ ] Rebuild backend image (includes new dependencies)
  ```bash
  docker-compose build backend
  ```

- [ ] Start all services
  ```bash
  docker-compose up -d
  ```

- [ ] Check service health
  ```bash
  docker-compose ps
  ```

### 5. Verify LDAP Server

- [ ] Check LDAP server logs
  ```bash
  docker logs ldap_server
  ```

- [ ] Test LDAP connection
  ```bash
  docker exec ldap_server ldapsearch -x -H ldap://localhost \
    -b "dc=cloud,dc=mes" -D "cn=admin,dc=cloud,dc=mes" -w admin
  ```

- [ ] Verify users exist
  ```bash
  docker exec ldap_server ldapsearch -x -H ldap://localhost \
    -b "ou=users,dc=cloud,dc=mes" -D "cn=admin,dc=cloud,dc=mes" -w admin
  ```

- [ ] Verify groups exist
  ```bash
  docker exec ldap_server ldapsearch -x -H ldap://localhost \
    -b "ou=groups,dc=cloud,dc=mes" -D "cn=admin,dc=cloud,dc=mes" -w admin
  ```

### 6. Verify Backend Integration

- [ ] Check backend logs
  ```bash
  docker logs flask_be
  ```

- [ ] Look for LDAP initialization message
  ```
  ✅ LDAP client initialized - using LDAP authentication
  ```

- [ ] Look for Vault connection
  ```
  ✅ Vault integration enabled - secrets managed by Vault
  ```

- [ ] Check database migration
  ```bash
  docker exec postgres_db psql -U postgres mes_local_cloud \
    -c "SELECT * FROM ldap_users;"
  ```

### 7. Test Authentication

- [ ] **Test admin login**
  ```bash
  curl -X POST http://localhost/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "password123"}'
  ```
  Expected: JWT token with role=admin

- [ ] **Test alice login**
  ```bash
  curl -X POST http://localhost/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "alice", "password": "password123"}'
  ```
  Expected: JWT token with role=user

- [ ] **Test moderator login**
  ```bash
  curl -X POST http://localhost/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "moderator", "password": "password123"}'
  ```
  Expected: JWT token with role=moderator

- [ ] **Test invalid credentials**
  ```bash
  curl -X POST http://localhost/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "wrongpassword"}'
  ```
  Expected: 401 error

### 8. Test Authorization

- [ ] **Test whoami endpoint**
  ```bash
  TOKEN="<jwt-token-from-login>"
  curl -H "Authorization: Bearer $TOKEN" http://localhost/auth/whoami
  ```

- [ ] **Test admin endpoints** (as admin)
  ```bash
  curl -H "Authorization: Bearer $TOKEN" http://localhost/admin/users
  ```

- [ ] **Test file operations** (as alice)
  ```bash
  curl -H "Authorization: Bearer $TOKEN" -F "file=@testfile.txt" \
    http://localhost/upload
  ```

### 9. Verify Data Persistence

- [ ] **Check user metadata in database**
  ```bash
  docker exec postgres_db psql -U postgres mes_local_cloud \
    -c "SELECT username, quota, last_login, email FROM ldap_users;"
  ```

- [ ] **Verify quotas are preserved**
  ```bash
  # Compare with backup_pre_ldap.sql
  ```

### 10. Security Verification

- [ ] **LDAP credentials not in environment variables**
  ```bash
  docker exec flask_be env | grep -i ldap
  # Should show nothing
  ```

- [ ] **LDAP credentials in Vault only**
  ```bash
  vault kv get secret/mes_local_cloud/ldap
  ```

- [ ] **No passwords in database**
  ```bash
  docker exec postgres_db psql -U postgres mes_local_cloud \
    -c "SELECT column_name FROM information_schema.columns \
        WHERE table_name='ldap_users';"
  # Should NOT include password_hash
  ```

## Post-Migration

### Change Default Passwords

- [ ] **Change LDAP admin password**
  ```bash
  docker exec ldap_server ldappasswd -x \
    -D "cn=admin,dc=cloud,dc=mes" -w admin \
    -s <new-strong-password> "cn=admin,dc=cloud,dc=mes"
  ```

- [ ] **Update Vault with new LDAP password**
  ```bash
  vault kv put secret/mes_local_cloud/ldap \
    url="ldap://ldap-server:389" \
    bind_dn="cn=admin,dc=cloud,dc=mes" \
    bind_password="<new-strong-password>" \
    base_dn="dc=cloud,dc=mes"
  ```

- [ ] **Change user passwords**
  ```bash
  docker exec ldap_server ldappasswd -x \
    -D "cn=admin,dc=cloud,dc=mes" -w <admin-password> \
    -s <new-password> "uid=admin,ou=users,dc=cloud,dc=mes"
  
  # Repeat for alice and moderator
  ```

### Documentation

- [ ] **Document LDAP structure**
  - User DN format: `uid=username,ou=users,dc=cloud,dc=mes`
  - Group DN format: `cn=groupname,ou=groups,dc=cloud,dc=mes`

- [ ] **Document role mapping**
  - cn=admins → admin role
  - cn=moderators → moderator role
  - cn=users → user role

- [ ] **Create user management procedures**
  - How to add new users
  - How to change passwords
  - How to assign roles (groups)

### Monitoring

- [ ] **Set up LDAP monitoring**
  ```bash
  # Check LDAP logs regularly
  docker logs ldap_server --tail 100
  ```

- [ ] **Set up authentication monitoring**
  ```bash
  # Check backend logs for auth failures
  docker logs flask_be | grep -i "authentication"
  ```

- [ ] **Set up alerts for failed logins**

### Backup

- [ ] **Backup LDAP data**
  ```bash
  docker exec ldap_server slapcat -v -l ldap_backup.ldif
  ```

- [ ] **Backup new database schema**
  ```bash
  docker exec postgres_db pg_dump -U postgres mes_local_cloud \
    > backup_post_ldap.sql
  ```

- [ ] **Document backup procedure**

## Rollback Plan

If issues arise, follow these steps to rollback:

1. **Stop services**
   ```bash
   docker-compose down
   ```

2. **Restore database backup**
   ```bash
   docker exec postgres_db psql -U postgres mes_local_cloud < backup_pre_ldap.sql
   ```

3. **Revert code changes**
   ```bash
   git checkout <previous-commit>
   ```

4. **Restart with old configuration**
   ```bash
   docker-compose up -d
   ```

## Troubleshooting

### LDAP Connection Issues

- [ ] Check LDAP server is running: `docker ps | grep ldap_server`
- [ ] Check LDAP logs: `docker logs ldap_server`
- [ ] Test connectivity: `docker exec backend ldapsearch ...`
- [ ] Verify Vault has LDAP secrets: `vault kv get secret/mes_local_cloud/ldap`

### Authentication Failures

- [ ] Verify user exists in LDAP
- [ ] Check user's group membership
- [ ] Check backend logs for LDAP errors
- [ ] Verify Vault is accessible from backend

### Database Issues

- [ ] Check ldap_users table exists
- [ ] Verify foreign key constraints updated
- [ ] Check database logs

## Sign-off

Migration completed by: ________________

Date: ________________

Verified by: ________________

Notes:
_________________________________
_________________________________
_________________________________
