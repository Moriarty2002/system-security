# Account Management Policy (AC-2)

## Document Control
- **Version**: 1.0
- **Effective Date**: 16 December 2025
- **Review Date**: December 2026
- **Owner**: Marcello Esposito
- **Approved By**: Lorenzo Aniello Alessandrella

## 1. Purpose
This policy establishes requirements for managing user and service accounts throughout their lifecycle to ensure accountability, least privilege, and timely removal of unnecessary access.

## 2. Scope
Applies to:
- User accounts in Keycloak (admin, moderator, user roles)
- Application user profiles in PostgreSQL database
- Service accounts (Vault AppRoles, MinIO service users)
- Temporary and emergency access accounts
- Shared infrastructure accounts (Vault, Keycloak administrators)

## 3. Policy Statements

### 3.1 Account Types and Authorization

#### 3.1.1 Individual User Accounts
- Each person assigned unique username in Keycloak
- Account creation requires administrator approval
- Username format: lowercase letters, numbers, underscore (e.g., john_doe)
- Accounts enabled only after identity verification

#### 3.1.2 Service Accounts
- **Vault AppRoles**: One per application component (e.g., mes-flask-app, apache-fe-app)
- **MinIO Service Users**: Dedicated user per application with bucket-specific access
- **Database Users**: Application-specific users with minimal required privileges
- Service account naming convention: `<app>-<component>-<purpose>`

#### 3.1.3 Shared Accounts
- Prohibited for individual users
- Emergency administrator accounts documented and audited
- Break-glass accounts secured and monitored

### 3.2 Account Management Requirements

#### 3.2.1 Account Creation
- User accounts created by administrators only through Keycloak Admin Console
- Initial role assignment: `user` (least privilege)
- Temporary password must be changed on first login
- User profile automatically synchronized to application database
- Service accounts created via automated scripts with approval

#### 3.2.2 Account Modification
- Role changes require administrator approval and justification
- Username changes prohibited (create new account instead)
- Email and profile updates logged in Keycloak audit
- Role escalation (user → moderator → admin) documented

#### 3.2.3 Account Disabling
- Accounts disabled immediately upon:
  - User termination or role change
  - 90 days of inactivity
  - Security policy violation
  - Repeated failed login attempts (automatic via Keycloak)
- Disabled accounts retained for 30 days before deletion
- Active sessions terminated on account disable

#### 3.2.4 Account Removal
- Permanent deletion after 30-day retention period
- Administrator approval required for deletion
- Audit logs preserved even after account deletion
- Associated data (files, logs) handled per data retention policy

### 3.3 Account Monitoring and Review

#### 3.3.1 Periodic Review
- Quarterly review of all user accounts and role assignments
- Annual review of service accounts and permissions
- Inactive accounts (>90 days) disabled automatically
- Privileged accounts (admin, moderator) reviewed monthly

#### 3.3.2 Automated Monitoring
- Failed login attempts tracked (max 5 before lockout)
- Unusual access patterns flagged for review
- Token usage logged for service accounts
- Vault secret access audited per AppRole

#### 3.3.3 Notification Requirements
- Users notified of account creation, modification, disabling
- Administrators alerted on privileged role assignments
- Security team notified of account lockouts or anomalies

### 3.4 Account Attributes

#### 3.4.1 Required Attributes
- Username (unique identifier)
- Email address (for notifications)
- Account status (enabled/disabled)
- Role assignment (admin/moderator/user)
- Creation date
- Last login timestamp

#### 3.4.2 Optional Attributes
- Display name
- Profile picture
- Department/organization
- Phone number

### 3.5 Special Account Types

#### 3.5.1 Temporary Accounts
- Maximum 30-day validity
- Expiration date mandatory
- Automatic disabling on expiration
- Purpose documented in account notes

#### 3.5.2 Emergency Accounts
- Pre-created for break-glass scenarios
- Stored credentials in sealed envelope
- Usage triggers immediate security review
- Changed after each use

#### 3.5.3 Guest/External Accounts
- Limited to user role only
- Cannot be escalated to moderator/admin
- Shorter token validity (2 minutes access, 15 minutes refresh)
- Stricter review cycle (weekly)

### 3.6 Service Account Management

#### 3.6.1 Vault AppRoles
- Created with minimum required Vault policies
- Token TTL: 20 minutes, Max TTL: 30 minutes
- Secret_id rotation every 90 days
- Role_id unique per service, never reused

#### 3.6.2 Database Service Accounts
- One per application/service
- Minimal schema/table permissions
- Credentials stored in Vault, never in code
- Connection pooling enforced to limit concurrent sessions

#### 3.6.3 Storage Service Accounts (MinIO)
- Bucket-specific access only
- No administrative privileges
- Access via IAM Roles Anywhere with certificates
- Certificate rotation every 24 hours

## 4. Roles and Responsibilities

### System Administrators
- Create/modify/disable user accounts in Keycloak
- Conduct quarterly account reviews
- Respond to account security incidents
- Maintain emergency account procedures

### Application Administrators
- Monitor account usage and access patterns
- Approve role change requests
- Generate account activity reports
- Coordinate with System Admins for privileged access

### Security Team
- Review audit logs monthly
- Investigate account anomalies
- Enforce account policies
- Conduct annual policy review

### Users
- Maintain account credentials securely
- Report unauthorized access
- Update profile information as needed
- Comply with acceptable use policy

## 5. Compliance and Enforcement
- Non-compliance may result in account suspension
- Violations documented in security incident log
- Corrective actions tracked to completion
- Policy reviewed annually and after security incidents

## 6. Related Policies
- AC-1: Access Control Policy
- IA-1: Identification and Authentication Policy
- IA-5: Authenticator Management Policy
- AU-2: Audit Events Policy
