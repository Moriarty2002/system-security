# Identification and Authentication Procedures

## Document Control
- **Version**: 1.0
- **Effective Date**: 10 December 2025
- **Review Date**: December 2026
- **Owner**: Marcello Esposito

## 1. Purpose
These procedures implement the I&A Policy and provide step-by-step guidance for authentication operations.

## 2. User Authentication Procedures

### 2.1 User Login Process
1. User navigates to https://localhost (or configured URL)
2. Application redirects to Keycloak SSO login page
3. User enters username and password
4. Keycloak validates credentials:
   - Checks against user database
   - Verifies account is enabled
   - Checks brute force protection status
5. On success:
   - Keycloak issues JWT access token (5-minute expiry)
   - Keycloak issues JWT refresh token (30-minute expiry)
   - User redirected to application with tokens
6. On failure:
   - Login attempt logged
   - Failure counter incremented
   - User shown error message
   - After 5 failures: account locked for 60 seconds

### 2.2 Token Validation Procedure

Backend (Flask) validates every API request:

1. Extract Authorization header (Bearer token)
2. Fetch Keycloak public key (JWKS endpoint)
3. Verify token signature using RS256
4. Check token expiry (verify_exp=True)
5. Extract user claims (username, roles)
6. Store user context in request (g.user_info)
7. Proceed with authorization check

**Implementation:** See `be_flask/src/keycloak_auth.py`

### 2.3 Token Refresh Procedure
1. Frontend detects token expiring soon (onTokenExpired event)
2. Calls Keycloak token refresh endpoint with refresh token
3. If refresh successful: New access token issued
4. If refresh fails: User logged out automatically

### 2.4 User Logout Procedure
1. User clicks logout button
2. Frontend calls `logout()` function:
   - Clears sessionStorage tokens
   - Calls `keycloak.logout()`
3. Keycloak invalidates refresh token
4. User redirected to login page

## 3. Account Management Procedures

### 3.1 New User Account Creation
1. Administrator logs into Keycloak Admin Console (https://localhost:8443)
2. Navigate to: Users > Add user
3. Enter required fields:
   - Username (unique)
   - Email
   - First name, Last name
   - Email verified: ON
   - Enabled: ON
4. Click Create
5. Navigate to Credentials tab
6. Set password:
   - Enter password (meets complexity requirements)
   - Temporary: OFF (unless password reset required)
7. Navigate to Role mappings tab
8. Assign appropriate role: user, moderator, or admin
9. Click Save

### 3.2 Account Disabling
1. Administrator logs into Keycloak Admin Console
2. Navigate to: Users > [select user]
3. Set Enabled: OFF
4. Click Save
5. User immediately loses access (existing tokens expire within 5 minutes)

### 3.3 Password Reset

**User-initiated:**
1. User clicks "Forgot Password" on login page
2. Enters username/email
3. Keycloak sends password reset email
4. User follows link and sets new password

**Administrator-initiated:**
1. Admin navigates to user's Credentials tab
2. Clicks "Set password"
3. Enters temporary password
4. Sets Temporary: ON
5. User must change password on next login

### 3.4 Account Lockout Resolution
1. Administrator checks brute force status:
   - Navigate to: Events > Login events
   - Filter by user
2. If legitimate user locked out:
   - Wait for lockout period to expire (auto-unlocks)
   - OR manually clear failures: Users > [user] > Credentials > Reset actions
3. If suspicious activity: Investigate before unlocking

## 4. Service Authentication Procedures

### 4.1 Vault AppRole Authentication

Backend Flask application:

1. Read VAULT_ROLE_ID and VAULT_SECRET_ID from environment
2. Call Vault API: POST /v1/auth/approle/login
3. Receive Vault token (1-hour TTL)
4. Store token and expiry time
5. Use token for subsequent Vault requests
6. Re-authenticate when token expires

**Implementation:** See `be_flask/src/vault_client.py`

### 4.2 AWS Roles Anywhere Authentication

S3 access:

1. Read X.509 certificate and private key from Vault
2. Call aws_signing_helper with:
   - Certificate
   - Private key
   - Trust anchor ARN
   - Profile ARN
   - Role ARN
3. Receive temporary AWS credentials (1-hour expiry)
4. Create S3 client with credentials
5. Refresh credentials when expired

**Implementation:** See `be_flask/src/s3_client.py`

## 5. Monitoring and Logging

### 5.1 Authentication Event Logging

**Keycloak events logged:**
- LOGIN (successful)
- LOGIN_ERROR (failed authentication)
- LOGOUT
- CODE_TO_TOKEN (token issuance)
- REFRESH_TOKEN

**Backend application logs:**
- Token validation success/failure
- User role extraction
- API access with user context

**Vault audit logs:**
- AppRole authentication
- Secret access
- Token renewal

### 5.2 Log Review Procedures
1. Weekly review of failed authentication attempts
2. Monthly review of all authentication events
3. Investigate:
   - Repeated failures from same user
   - Unusual authentication times
   - Geographic anomalies (if IP geolocation enabled)
   - Multiple rapid login attempts

## 6. Incident Response

### 6.1 Suspected Credential Compromise
1. Immediately disable affected account
2. Revoke all active tokens:
   - Keycloak: Sessions > [user] > Logout
   - Vault: Revoke affected AppRole secret-id
3. Force password reset
4. Review access logs for unauthorized activity
5. Investigate compromise source
6. Document incident

### 6.2 Brute Force Attack Detection
1. Monitor for excessive failed logins
2. If attack detected:
   - Confirm brute force protection active
   - Consider temporary IP blocking (if available)
   - Alert security team
3. Review attack patterns
4. Update defenses if needed

## 7. Configuration Management

### 7.1 Keycloak Configuration Backup

**Schedule:** Weekly

```bash
cd keycloak-infrastructure
docker exec shared-keycloak-server /opt/keycloak/bin/kc.sh export \
  --file /tmp/realm-export.json \
  --realm mes-local-cloud
docker cp shared-keycloak-server:/tmp/realm-export.json \
  ./backup/realm-export-$(date +%Y%m%d).json
```

### 7.2 Vault AppRole Rotation

**Schedule:** Quarterly

```bash
cd 4_three_tier_app/vault/scripts
./rotate-secret-id.sh
# Updates VAULT_SECRET_ID in .env
# Restart backend: docker compose restart backend
```

## 8. Testing and Validation

### 8.1 Authentication Testing

**Monthly validation:**
1. Test successful login with valid credentials
2. Test failed login with invalid credentials
3. Verify brute force protection activates after 5 failures
4. Test token refresh mechanism
5. Test logout functionality
6. Verify token expiry enforcement

### 8.2 Service Authentication Testing

**Quarterly validation:**
1. Test Vault AppRole authentication
2. Test AWS Roles Anywhere authentication
3. Verify automatic credential renewal
4. Test authentication failure handling

## 9. Training Requirements
- New administrators: Complete Keycloak training before account management
- Annual refresher: All administrators review I&A procedures
- Users: Receive authentication security awareness training

## 10. Procedure Review
- Procedures reviewed annually (December each year)
- Updated when technical changes occur
- Updates coordinated with policy reviews
- Version history maintained

## Revision History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 10 Dec 2025 | Marcello Esposito | Initial procedures creation |
