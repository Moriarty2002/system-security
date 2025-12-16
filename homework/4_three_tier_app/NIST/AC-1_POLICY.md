# Access Control Policy (AC-1)

## Document Control
- **Version**: 1.0
- **Effective Date**: 16 December 2025
- **Review Date**: December 2026
- **Owner**: Marcello Esposito
- **Approved By**: Lorenzo Aniello Alessandrella

## 1. Purpose
This policy establishes access control requirements for the Secure File Storage Service to ensure only authorized users and services can access system resources based on their roles and responsibilities.

## 2. Scope
Applies to:
- Three-tier application (Apache frontend, Flask backend, PostgreSQL database, MinIO storage)
- Keycloak identity provider (shared infrastructure)
- HashiCorp Vault secrets management (shared infrastructure)
- All user accounts (admin, moderator, user)
- Service accounts (AppRole-based machine authentication)
- Container-level security controls

## 3. Policy Statements

### 3.1 Role-Based Access Control (RBAC)
- **Admin**: Full system access including user management, file operations, system configuration
- **Moderator**: File management for all users, user profile viewing, limited administrative functions
- **User**: Own files management, profile management, read-only access to shared resources
- Roles enforced through Keycloak realm/client roles validated in Flask backend

### 3.2 User Access Management
- All users authenticate via centralized Keycloak SSO
- Access tokens expire after 5 minutes, refresh tokens after 30 minutes
- Token validation occurs on every API request using RS256 signature verification
- User profiles synchronized between Keycloak and application database
- Shared accounts prohibited except for authorized service accounts

### 3.3 Service-to-Service Authentication
- **Backend → Vault**: AppRole authentication with role-specific policies
  - Unique role_id and secret_id per service
  - Secrets stored at namespaced paths (e.g., `secret/mes_local_cloud/`)
- **Backend → Database**: Credentials fetched from Vault at runtime
- **Backend → MinIO**: AWS IAM Roles Anywhere with certificate-based authentication
- **Apache → Backend**: Internal network communication over app_net
- No hardcoded credentials in code or configuration files

### 3.4 Network Segmentation
- **shared_vault_net**: Isolated Vault access (172.30.0.0/16)
- **keycloak_net**: Keycloak and database communication
- **app_net**: Application tier communication
- Services only join networks required for their function

### 3.5 Container Security Controls
- **Least Privilege**: Minimal Linux capabilities (CAP_DROP ALL, selective CAP_ADD)
- **Read-Only Filesystems**: Containers run with read_only: true
- **Resource Limits**: Memory, CPU, PID limits enforced
- **No New Privileges**: security_opt: no-new-privileges:true
- **Non-Root Execution**: Services run as unprivileged users (UID 1000)

### 3.6 Secrets Management
- All secrets managed by HashiCorp Vault
- Database credentials, API keys, certificates stored in Vault
- Policy-based access control for secret retrieval
- Audit logging enabled for all Vault operations
- Secrets rotation supported through Vault dynamic secrets

### 3.7 Access Logging and Monitoring
- Flask backend logs all authentication attempts and authorization decisions
- Vault audit logs track secret access
- Keycloak logs user login/logout events
- Docker logs retained (max-size: 10m, max-file: 3)

### 3.8 Account Lockout
- Maximum 5 failed login attempts enforced by Keycloak
- 60-second progressive lockout after failed attempts
- 12-hour failure reset period

## 4. Roles and Responsibilities

### System Administrator
- Manages Vault policies and AppRoles
- Configures Keycloak realms, clients, and role mappings
- Reviews access logs and audit trails
- Performs annual policy review

### Application Administrator
- Assigns user roles (admin/moderator/user)
- Monitors application access logs
- Responds to access-related incidents

### Users
- Maintain secure authentication credentials
- Report suspicious access attempts
- Use access only for authorized purposes

## 5. Compliance and Review
- Policy reviewed annually or when significant changes occur
- Access rights reviewed quarterly
- Audit logs retained for 90 days minimum
- Compliance with NIST 800-53 AC family controls

## 6. Related Policies
- IA-1: Identification and Authentication Policy
- SC-1: System and Communications Protection Policy
- AC-20: Use of External Systems
