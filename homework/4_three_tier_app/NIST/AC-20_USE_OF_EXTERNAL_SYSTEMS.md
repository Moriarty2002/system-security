# AC-20 External Systems Use Policy

## Approved External Systems

### 1. AWS S3 (Cloud Object Storage)
**Purpose:** File storage backend for user uploads  
**Authorization:** Approved for production use  
**Security Requirements:**
- TLS 1.2+ encryption for all API calls
- IAM Roles Anywhere with X.509 certificate authentication
- Temporary credentials (max 1-hour TTL)
- Bucket policies enforce least privilege
- Server-side encryption enabled (AES-256 or KMS)

**Permitted Data Classifications:**
- Public data (user-uploaded files)
- Internal data (non-sensitive user content)

**Prohibited Data:**
- Personal Identifiable Information (PII) without encryption
- Payment card data (PCI-DSS scope)
- Health information (HIPAA scope)

**User Responsibilities:**
- Do not store passwords or secrets in files
- Files subject to quota limits (per user)
- Comply with acceptable use policy

### 2. HashiCorp Vault (Secrets Management)
**Purpose:** Centralized secrets storage  
**Authorization:** Internal shared infrastructure  
**Security Requirements:**
- TLS 1.3 encryption
- AppRole authentication
- Policy-based RBAC
- Audit logging enabled

### 3. Keycloak (Identity Management)
**Purpose:** User authentication and authorization  
**Authorization:** Internal shared infrastructure  
**Security Requirements:**
- TLS 1.3 encryption
- OIDC protocol
- Short-lived tokens (5-min access, 30-min refresh)

## Prohibited External Systems
- Personal cloud storage (Dropbox, Google Drive, etc.)
- Unapproved file sharing services
- Third-party APIs without security review
- Unencrypted FTP servers

## Portable Storage Device Policy (AC-20(2))
**Restrictions:**
- USB drives, external HDDs must be encrypted (BitLocker, LUKS, FileVault)
- Copying files from application to portable devices requires:
  - User authentication
  - Logging of download activity
  - Malware scan on portable device