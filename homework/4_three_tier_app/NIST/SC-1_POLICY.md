# System and Communications Protection Policy

## Document Control
- **Version**: 1.0
- **Effective Date**: 12 December 2025
- **Review Date**: December 2026
- **Owner**: Marcello Esposito
- **Approved By**: Lorenzo Aniello Alessandrella

## 1. Purpose
This policy establishes requirements for protecting system communications and boundaries in the Secure File Storage Service to ensure confidentiality and integrity of data in transit and at rest.

## 2. Scope
Applies to:
- All network communications (internal and external)
- Vault infrastructure for secrets management
- Keycloak infrastructure for authentication
- Three-tier application stack (Apache, Flask, PostgreSQL)
- All cryptographic implementations

## 3. Policy Statements

### 3.1 Transmission Security
- All external communications must use TLS 1.3 or higher
- HTTP traffic must redirect to HTTPS
- Modern cipher suites required (X25519, prime256v1, secp384r1)
- Certificate-based authentication via Vault PKI
- HSTS enforced with minimum 1-year max-age

### 3.2 Network Boundary Protection
- Network segmentation implemented via isolated Docker networks
- Reverse proxy (Apache) serves as single external entry point
- Internal services not directly exposed to external networks
- Database accessible only via internal application network
- Minimal port exposure (80, 443 to localhost only)

### 3.3 Cryptographic Protection
- Strong cryptography required for all sensitive data
- Secrets encrypted at rest in HashiCorp Vault
- JWT tokens signed with RS256 algorithm
- Password hashing via bcrypt or Argon2 (Keycloak)
- No hardcoded cryptographic keys in code or configuration

### 3.4 Key Management
- Vault PKI manages all TLS certificates
- AppRole authentication for service-to-service communication
- Least privilege access via Vault policies
- Token expiration enforced (5-minute access, 30-minute refresh)

### 3.5 Security Monitoring
- Audit logging enabled for Vault operations
- Authentication events logged in Keycloak
- Application logs retained with 10MB rotation, 3-file retention
- Security events reviewed during incident investigations

## 4. Roles and Responsibilities

### 4.1 System Owner
- Overall accountability for system and communications protection
- Approves policy updates and exceptions
- Ensures resources for implementation

### 4.2 Security Administrator
- Implements and maintains cryptographic controls
- Manages Vault and certificate infrastructure
- Configures network segmentation
- Monitors security logs and responds to incidents

### 4.3 Application Developers
- Follow secure coding practices
- Use Vault for all secret retrieval
- Implement TLS for all communications
- Never hardcode credentials

## 5. Compliance
This policy supports compliance with:
- NIST SP 800-53 Rev 5 (SC family controls)
- SC-7 (Boundary Protection)
- SC-8 (Transmission Confidentiality)
- SC-12 (Cryptographic Key Management)
- SC-13 (Cryptographic Protection)
- SC-28 (Protection of Information at Rest)

## 6. Exceptions
- Exception requests submitted in writing with justification
- Compensating controls required
- Temporary exceptions limited to 90 days
- All exceptions require System Owner approval

## 7. Policy Review
- Policy reviewed annually (December each year)
- Updated when architecture changes or incidents occur
- Updates require System Owner approval
- Version history maintained in document control

## 8. Related Documents
- SC-1 Procedures Document
- IA-1 Policy and Procedures
- Vault Infrastructure Documentation
- Keycloak Infrastructure Documentation
