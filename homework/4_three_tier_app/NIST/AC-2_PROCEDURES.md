# Account Management Procedures (AC-2)

## Document Control
- **Version**: 1.0
- **Effective Date**: 16 December 2025
- **Review Date**: December 2026
- **Owner**: Marcello Esposito

## 1. Purpose
These procedures implement the Account Management Policy (AC-2) providing step-by-step guidance for creating, modifying, monitoring, and removing accounts.

## 2. User Account Lifecycle Procedures

### 2.1 Create New User Account

**Prerequisites**: Administrator access to Keycloak Admin Console

**Procedure**:
1. Login to Keycloak Admin Console: http://localhost:8080
   - Username: `admin` (from [keycloak-infrastructure/secrets/admin_username.txt](../../../keycloak-infrastructure/secrets/admin_username.txt))
   - Password: (from [keycloak-infrastructure/secrets/admin_password.txt](../../../keycloak-infrastructure/secrets/admin_password.txt))

2. Navigate to realm: `mes_local_cloud`

3. Click **Users** (left sidebar) → **Add User**

4. Fill required fields:
   - **Username**: lowercase, alphanumeric + underscore (e.g., `alice_smith`)
   - **Email**: valid email address
   - **Enabled**: ON
   - **Email Verified**: ON (if email confirmed)

5. Click **Save**

6. Navigate to **Credentials** tab:
   - Click **Set Password**
   - Enter temporary password
   - **Temporary**: ON (forces password change on first login)
   - Click **Save**

7. Navigate to **Role Mappings** tab:
   - Default role: `user` (already assigned)
   - For elevated privileges:
     - **Realm Roles**: Add `admin` or `moderator`
     - **Client Roles** (mes-file-storage): Add `admin`, `moderator`, or leave as `user`

8. Document account creation:
   - Username: `alice_smith`
   - Role: `user`
   - Created by: `admin`
   - Date: 2025-12-16
   - Purpose: Standard user access

**Result**: User can login at https://localhost and will be prompted to change password

**Implementation Reference**: [keycloak-infrastructure/scripts/init-keycloak.sh](../../../keycloak-infrastructure/scripts/init-keycloak.sh) (automated setup)

### 2.2 Modify User Account Role

**Scenario**: Promote user to moderator

**Procedure**:
1. Keycloak Admin Console → **Users**
2. Search for username
3. Click username to open details
4. **Role Mappings** tab
5. **Available Roles** → Select `moderator` → Click **Add selected**
6. Verify under **Assigned Roles**: `moderator` appears
7. Changes effective immediately (next API request validates new role)

**Verification**:
```bash
# User logs in, checks their role via API
curl -X GET https://localhost/api/profile \
  -H "Authorization: Bearer <token>"
# Response should show "role": "moderator"
```

### 2.3 Disable User Account

**Scenarios**: User termination, security violation, inactivity

**Procedure**:
1. Keycloak Admin Console → **Users** → Search user
2. Click username
3. **Details** tab
4. Toggle **Enabled** to OFF
5. Click **Save**
6. **Sessions** tab → **Logout all** (force immediate logout)

**Result**: 
- User cannot login
- Active tokens remain valid until expiry (max 5 minutes)
- Force immediate logout by terminating sessions

**Automated Inactivity Disabling**:
```bash
# Script to disable accounts inactive >90 days (run monthly)
# keycloak-infrastructure/scripts/disable-inactive-accounts.sh
# (Implementation: Query last login via Keycloak API, disable if >90 days)
```

### 2.4 Delete User Account

**Prerequisites**: Account disabled for 30+ days, approval obtained

**Procedure**:
1. Verify account disabled and retention period elapsed
2. Backup audit logs:
   ```bash
   # Export user activity logs before deletion
   docker exec flask_be python -c "from src.models import db, UserProfile; \
     user = UserProfile.query.filter_by(username='alice_smith').first(); \
     print(f'User ID: {user.keycloak_id}, Files: {len(user.files)}')"
   ```

3. Handle user data:
   - Option A: Delete all user files
   - Option B: Transfer files to another user
   - Option C: Archive files (retain metadata)

4. Keycloak Admin Console → **Users** → Search user
5. Click username → **Actions** → **Delete**
6. Confirm deletion

7. Database cleanup (automatic on next user sync):
   - User profile soft-deleted or marked inactive
   - File ownership records updated

**Note**: Audit logs retained regardless of account deletion

### 2.5 Create Temporary Account

**Use Case**: External auditor, contractor, short-term access

**Procedure**:
1. Follow standard account creation (Section 2.1)
2. After account created, set expiration:
   - **Attributes** tab → **Add Attribute**
   - Key: `expiration_date`
   - Value: `2025-12-31T23:59:59Z` (ISO 8601 format)
   - Click **Save**

3. Schedule automatic disabling:
   ```bash
   # Add to cron job (run daily)
   # Check expiration_date attribute, disable if expired
   # Script: keycloak-infrastructure/scripts/check-account-expiry.sh
   ```

4. Document temporary access:
   - Purpose: Security audit
   - Requestor: Lorenzo Alessandrella
   - Duration: 30 days
   - Expiration: 2025-12-31

## 3. Service Account Procedures

### 3.1 Create Vault AppRole for New Service

**Script**: [vault/scripts/setup-vault-app.sh](../vault/scripts/setup-vault-app.sh)

**Manual Procedure**:
1. Connect to Vault:
   ```bash
   export VAULT_ADDR='https://localhost:8200'
   export VAULT_TOKEN=$(jq -r '.root_token' ../vault-infrastructure/scripts/vault-keys.json)
   export VAULT_SKIP_VERIFY=1
   ```

2. Create policy file `policies/new-service-policy.hcl`:
   ```hcl
   # Policy for new-service AppRole
   path "secret/data/mes_local_cloud/new-service/*" {
     capabilities = ["read", "list"]
   }
   
   path "secret/metadata/mes_local_cloud/new-service/*" {
     capabilities = ["list"]
   }
   ```

3. Upload policy:
   ```bash
   vault policy write new-service-policy policies/new-service-policy.hcl
   ```

4. Create AppRole:
   ```bash
   vault write auth/approle/role/new-service-app \
     token_ttl=20m \
     token_max_ttl=30m \
     token_policies="new-service-policy" \
     bind_secret_id=true
   ```

5. Retrieve role_id and secret_id:
   ```bash
   vault read auth/approle/role/new-service-app/role-id
   vault write -f auth/approle/role/new-service-app/secret-id
   ```

6. Store credentials securely:
   - Add to service's `.env` file
   - Or use Docker secrets
   - Never commit to version control

7. Document service account:
   - AppRole: `new-service-app`
   - Policy: `new-service-policy`
   - Created: 2025-12-16
   - Purpose: Database access for new-service component

### 3.2 Rotate Service Account Credentials

**Frequency**: Every 90 days or after suspected compromise

**Procedure**:
1. Generate new secret_id:
   ```bash
   vault write -f auth/approle/role/mes-flask-app/secret-id
   # Output: secret_id and secret_id_accessor
   ```

2. Update service configuration:
   - Edit `.env` file: `VAULT_SECRET_ID=<new_secret_id>`
   - Or update Docker secret

3. Restart service:
   ```bash
   docker restart flask_be
   ```

4. Verify service can authenticate:
   ```bash
   docker logs flask_be | grep "Vault authentication successful"
   ```

5. Revoke old secret_id (optional, expires automatically):
   ```bash
   vault write auth/approle/role/mes-flask-app/secret-id-accessor/destroy \
     secret_id_accessor=<old_accessor>
   ```

### 3.3 Create MinIO Service Account

**Implementation**: [minio/scripts/setup-minio-user.sh](../minio/scripts/setup-minio-user.sh)

**Manual Procedure**:
1. Access MinIO console: http://localhost:9001
2. Login with admin credentials (from Vault)
3. **Identity** → **Users** → **Create User**
4. Set username: `mes-file-storage-app`
5. Generate access key and secret key
6. Assign policy: `mes-bucket-rw` (read/write to specific bucket only)
7. Store credentials in Vault:
   ```bash
   vault kv put secret/mes_local_cloud/minio \
     MINIO_ACCESS_KEY=<access_key> \
     MINIO_SECRET_KEY=<secret_key>
   ```

## 4. Account Monitoring Procedures

### 4.1 Review Failed Login Attempts

**Frequency**: Daily

**Procedure**:
1. Keycloak Admin Console → **Events** → **Login Events**
2. Filter by: **Event Type** = `LOGIN_ERROR`
3. Review failed attempts:
   - Multiple failures from same user: Possible credential issue
   - Multiple failures from same IP: Possible brute force attack
   - Failed admin logins: Security incident

4. Actions:
   - Contact user if legitimate account locked
   - Block IP if brute force detected
   - Force password reset if credentials suspected compromised

**Automated Monitoring**:
```bash
# Script: scripts/monitor-failed-logins.sh
# Check Keycloak logs for failed attempts, alert if threshold exceeded
docker logs shared-keycloak-server 2>&1 | grep "LOGIN_ERROR" | tail -20
```

### 4.2 Quarterly Account Review

**Frequency**: Every 90 days

**Procedure**:
1. Export user list from Keycloak:
   - Admin Console → **Users** → **Export** (or use API)

2. Create review spreadsheet:
   | Username | Role | Last Login | Status | Action |
   |----------|------|------------|--------|--------|
   | alice | user | 2025-12-15 | Active | No change |
   | bob | moderator | 2025-09-01 | Inactive | Disable |
   | admin | admin | 2025-12-16 | Active | Review |

3. Check each account:
   - Last login < 90 days: Active, no action
   - Last login > 90 days: Disable account
   - Privileged accounts (admin/moderator): Verify still required

4. Update accounts:
   - Disable inactive users (Section 2.3)
   - Remove unnecessary role assignments
   - Document justification for privileged access

5. Generate report:
   - Total accounts: 25
   - Active: 20
   - Disabled: 5
   - Role changes: 2 (bob: moderator → user)
   - Deletions: 1 (charlie, disabled >30 days)

6. Submit report to security team

**Implementation**: [scripts/quarterly-account-review.sh](../scripts/quarterly-account-review.sh)

### 4.3 Monitor Privileged Account Activity

**Frequency**: Weekly for admin/moderator accounts

**Procedure**:
1. Check Keycloak audit logs:
   - Admin Console → **Events** → **Admin Events**
   - Filter by admin username
   - Review actions: user creation, role changes, configuration modifications

2. Check application logs:
   ```bash
   # Admin/moderator API calls
   docker logs flask_be | grep "role.*admin\|moderator"
   ```

3. Check Vault audit logs:
   ```bash
   # Vault secret access by privileged users
   docker exec shared_vault_server cat /vault/logs/audit.log | \
     jq 'select(.request.path | contains("secret"))'
   ```

4. Anomaly detection:
   - Admin actions outside business hours
   - Unusual number of account creations
   - Bulk role assignments
   - Access to secrets not related to admin's responsibilities

5. Document findings and escalate suspicious activity

## 5. Emergency Procedures

### 5.1 Emergency Account Lockout

**Scenario**: Compromised account detected

**Immediate Actions**:
1. Disable account in Keycloak (Section 2.3)
2. Logout all sessions
3. Revoke active tokens (tokens expire in 5 minutes max)
4. Review audit logs for unauthorized actions
5. Notify security team and user
6. Change user password
7. Re-enable account only after investigation complete

### 5.2 Emergency Administrator Access

**Scenario**: Primary admin account unavailable

**Procedure**:
1. Locate break-glass credentials:
   - Sealed envelope in secure location
   - Or Vault emergency token

2. Access Keycloak Admin Console with emergency account

3. Perform necessary administrative tasks

4. Document all actions taken with emergency account

5. Rotate emergency account credentials after use:
   ```bash
   # Change emergency admin password
   # Update sealed envelope
   # Log usage in security incident report
   ```

## 6. Automation Scripts

### 6.1 Nightly Account Sync

**Script**: [be_flask/scripts/sync-keycloak-users.py](../be_flask/scripts/sync-keycloak-users.py)

**Purpose**: Synchronize Keycloak users to application database

**Schedule**: Daily at 2:00 AM (cron job)

**Actions**:
- Fetch all users from Keycloak API
- Create UserProfile in database if not exists
- Update user status (enabled/disabled)
- No deletion (soft delete only)

### 6.2 Automated Inactivity Check

**Script**: [keycloak-infrastructure/scripts/disable-inactive-accounts.sh](../../../keycloak-infrastructure/scripts/disable-inactive-accounts.sh)

**Schedule**: Monthly

**Logic**:
- Query last login timestamp from Keycloak
- If last_login > 90 days and status = enabled:
  - Disable account
  - Send notification email
  - Log action

### 6.3 Service Account Credential Expiry Check

**Script**: [vault/scripts/check-approle-expiry.sh](../vault/scripts/check-approle-expiry.sh)

**Schedule**: Weekly

**Logic**:
- Query Vault for secret_id creation dates
- If secret_id > 90 days old:
  - Alert administrators
  - Recommend rotation (Section 3.2)

## 7. Reporting

### 7.1 Monthly Account Summary Report

**Generated**: First day of each month

**Contents**:
- Total accounts: X
- New accounts created: Y
- Accounts disabled: Z
- Accounts deleted: A
- Role changes: B
- Failed login attempts: C
- Service accounts: D

**Distribution**: Security team, management

**Tool**: [scripts/generate-account-report.sh](../scripts/generate-account-report.sh)

## 8. Related Procedures
- AC-1: Access Control Procedures
- IA-1: Identification and Authentication Procedures
- IA-5: Authenticator Management Procedures
- AU-2: Audit Events Procedures
