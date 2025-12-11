# Identification and Authentication Policy

## Document Control
- **Version**: 1.0
- **Effective Date**: 10 December 2025
- **Review Date**: December 2026
- **Owner**: Marcello Esposito
- **Approved By**: Lorenzo Aniello Alessandrella

## 1. Purpose
This policy establishes requirements for identifying and authenticating users accessing the Secure File Storage Service to ensure only authorized individuals can access system resources.

## 2. Scope
Applies to:
- All users accessing the application (administrators, moderators, standard users)
- Service accounts and machine-to-machine authentication
- All authentication mechanisms (web UI, API, internal services)
- External identity providers (Keycloak)

## 3. Policy Statements

### 3.1 User Identification
- All users must be uniquely identified before authentication
- Usernames must be unique within the system
- Service accounts must be clearly distinguishable from user accounts
- Shared accounts are prohibited except where technically justified and approved

### 3.2 Authentication Requirements
- All access requires successful authentication
- Users authenticate via Keycloak SSO using username and password
- Service accounts use certificate-based authentication (AppRole, Roles Anywhere)
- Authentication credentials are never stored in application code or configuration files

### 3.3 Password Requirements
- Managed by Keycloak identity provider
- Minimum password requirements enforced by Keycloak policy
- Passwords stored as salted hashes (bcrypt/Argon2)
- Password reset requires identity verification

### 3.4 Token-Based Access
- Access tokens expire after 5 minutes
- Refresh tokens expire after 30 minutes of inactivity
- Tokens use RS256 signature algorithm
- Token validation occurs on every API request

### 3.5 Brute Force Protection
- Maximum 5 failed login attempts before account lockout
- 60-second wait increment between attempts
- 12-hour failure reset period
- Administrative accounts subject to same restrictions

### 3.6 Role-Based Access Control
- Users assigned roles: user, moderator, or admin
- Roles determine authorization scope after authentication
- Role assignments managed through Keycloak admin console
- Least privilege principle applied to all role assignments

## 4. Roles and Responsibilities

### 4.1 System Owner
- Overall accountability for I&A policy
- Approves policy updates and exceptions
- Ensures adequate resources for implementation

### 4.2 Security Administrator
- Implements and maintains I&A mechanisms
- Configures Keycloak and authentication services
- Monitors authentication logs for anomalies
- Responds to authentication security incidents

### 4.3 Users
- Protect authentication credentials
- Report suspected credential compromise immediately
- Comply with password and access requirements
- Logout when session complete

### 4.4 Keycloak Administrator
- Manages user accounts and roles
- Configures password policies
- Enables/disables accounts as needed
- Reviews authentication audit logs

## 5. Compliance
This policy supports compliance with:
- NIST SP 800-53 Rev 5 (IA family controls)

## 6. Exceptions
- Exception requests must be submitted in writing
- Justification and compensating controls required
- Temporary exceptions limited to 90 days maximum
- All exceptions require System Owner approval

## 7. Policy Review
- Policy reviewed annually (December each year)
- Updated when significant architecture changes occur
- Updates require System Owner approval
- Version history maintained in document control section

## 8. Related Documents
- IA-1 Procedures Document
- AC-2 Account Management Policy
- AC-7 Unsuccessful Login Attempts Policy
- IA-5 Authenticator Management Procedures

## 9. Enforcement
Violations may result in:
- Account suspension
- Access revocation
- Disciplinary action per organizational policy

## Revision History
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 10 Dec 2025 | Marcello Esposito | Initial policy creation |
