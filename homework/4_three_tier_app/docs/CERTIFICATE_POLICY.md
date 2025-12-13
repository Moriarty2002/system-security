# Certificate Policy

**NIST 800-53 SC-17 Compliance Documentation**  
**Organization:** Local Cloud Project  
**Version:** 1.0  
**Last Updated:** December 12, 2025  
**Compliance Level:** MODERATE  
**Next Review:** June 12, 2026

---

## 1. Purpose and Scope

This Certificate Policy defines the requirements and procedures for issuing, managing, and validating public key infrastructure (PKI) certificates within the Local Cloud system. This policy applies to all certificates used for:

- **TLS/SSL server authentication** (Apache web server, Keycloak IdP)
- **Internal service authentication** (Backend-to-service communications)
- **Certificate-based trust establishment** between system components

This policy implements NIST 800-53 SC-17 requirements for public key infrastructure certificates at the MODERATE security categorization level.

---

## 2. Certificate Authority Information

### 2.1 Internal Certificate Authority

**CA Name:** Vault PKI CA (`pki_localhost`)  
**CA Type:** Private/Internal Certificate Authority  
**Provider:** HashiCorp Vault PKI Secrets Engine  
**Purpose:** Issue certificates for internal services within the Local Cloud application ecosystem  
**Operational Status:** Active  

**CA Characteristics:**
- **Key Algorithm:** RSA
- **Key Size:** 2048 bits minimum (configurable to 4096 bits)
- **Signature Algorithm:** SHA-256 with RSA
- **CA Certificate Validity:** Configured during PKI initialization
- **Hierarchy:** Single-tier (root CA for internal use)

**CA Location:**
- **Vault Server:** `shared_vault_server` (container)
- **PKI Engine Path:** `pki_localhost/`
- **API Endpoint:** `https://shared_vault_server:8200/v1/pki_localhost/`

### 2.2 CA Trust Model

The Vault PKI CA operates as a **trusted internal certificate authority** for the Local Cloud application. All system components are configured to trust certificates issued by this CA through:

1. **Automatic CA installation** via `install_ca.sh` script at container startup
2. **System trust store integration** using `update-ca-certificates`
3. **Application-level trust configuration** (Python `REQUESTS_CA_BUNDLE`, Apache SSL configuration)

---

## 3. Certificate Issuance Policy

### 3.1 Certificate Types and Purposes

The following certificate types are authorized for issuance:

#### **TLS Server Certificates**
- **Purpose:** Authenticate web servers and encrypt HTTPS traffic
- **Issued To:** Apache frontend, Keycloak server
- **Key Usage:** Digital Signature, Key Encipherment
- **Extended Key Usage:** Server Authentication (id-kp-serverAuth)

#### **Internal Service Certificates**
- **Purpose:** Secure inter-service communication
- **Issued To:** Backend services requiring mutual TLS
- **Key Usage:** Digital Signature, Key Encipherment
- **Extended Key Usage:** Server Authentication, Client Authentication

### 3.2 Certificate Issuance Requirements

All certificates issued under this policy must meet the following requirements:

#### **3.2.1 Cryptographic Requirements**

| Parameter | Requirement | Rationale |
|-----------|-------------|-----------|
| **Key Algorithm** | RSA or ECDSA | Industry standard algorithms |
| **RSA Key Size** | 2048 bits minimum | NIST SP 800-57 recommendation |
| **ECDSA Curve** | P-256 or P-384 | NIST-approved curves |
| **Signature Algorithm** | SHA-256 or stronger | SHA-1 deprecated |
| **Random Number Generation** | FIPS 140-2 compliant | Cryptographic security |

#### **3.2.2 Validity Period Requirements**

| Certificate Type | Default TTL | Maximum TTL | Rationale |
|------------------|-------------|-------------|-----------|
| **TLS Server** | 90 days (2160h) | 1 year (8760h) | Balance security and operational overhead |
| **Internal Service** | 90 days (2160h) | 1 year (8760h) | Frequent rotation reduces compromise risk |

**Renewal Policy:** Certificates should be renewed 30 days before expiration to prevent service disruption.

#### **3.2.3 Subject Name Requirements**

**Common Name (CN):**
- Must match the primary DNS name or IP address of the service
- Examples: `localhost`, `shared-keycloak-server`, `apache_fe`

**Subject Alternative Names (SAN):**
- Must include all DNS names and IP addresses used to access the service
- Wildcard certificates (`*.domain.com`) permitted for development environments only
- Examples: `DNS:localhost, DNS:shared-keycloak-server, IP:127.0.0.1`

**Allowed Domains:**
- `localhost` (development)
- `*.local` (internal services)
- `*.keycloak.local` (Keycloak services)
- Container names (e.g., `apache_fe`, `flask_be`, `shared-keycloak-server`)

**Prohibited:**
- Public domain names not owned by the organization
- Expired or reserved domains
- Domains violating DNS naming conventions

### 3.3 Certificate Request and Approval Process

#### **3.3.1 Automated Issuance (Standard Process)**

For standard service certificates, automated issuance is permitted:

1. **Service Startup:** Container initialization triggers certificate request
2. **Vault Authentication:** Service authenticates using AppRole credentials
3. **Certificate Request:** Vault PKI issues certificate via configured role
4. **Validation:** Vault verifies request against role constraints
5. **Issuance:** Certificate and private key generated and returned
6. **Installation:** Service configures certificate for immediate use

**Implementation Files:**
- Apache: `apache/scripts/entrypoint.sh`
- Keycloak: `keycloak-infrastructure/scripts/keycloak-entrypoint.sh`
- Backend: `be_flask/scripts/install_ca.sh`

#### **3.3.2 Manual Issuance (Exception Process)**

For special cases requiring manual review:

1. **Request Submission:** Administrator submits certificate request
2. **Security Review:** Verify domain ownership and legitimate use case
3. **Approval:** Security officer or project lead approves request
4. **Issuance:** Execute Vault command to generate certificate
5. **Documentation:** Record issuance in certificate inventory

### 3.4 Certificate Roles (Vault PKI)

Vault PKI roles define templates for certificate issuance:

#### **apache-server-localhost**
```bash
# Configuration: vault/scripts/setup-vault-app.sh
allowed_domains="localhost,*.local"
allow_subdomains=true
allow_bare_domains=true
allow_localhost=true
allow_ip_sans=true
max_ttl="8760h"        # 1 year
ttl="2160h"            # 90 days
key_type="rsa"
key_bits=2048
require_cn=false
```

#### **keycloak-server-localhost**
```bash
# Configuration: keycloak-infrastructure/scripts/setup-shared-pki-role.sh
allowed_domains="localhost,keycloak,shared-keycloak-server,*.local,*.keycloak.local"
allow_subdomains=true
allow_bare_domains=true
allow_localhost=true
allow_ip_sans=true
max_ttl="8760h"        # 1 year
ttl="2160h"            # 90 days
key_type="rsa"
key_bits=2048
require_cn=false
```

**Access Control:** Only services with appropriate Vault policies can issue certificates from these roles (see: `vault/policies/pki-policy.hcl`).

---

## 4. Certificate Validation Policy

### 4.1 Certificate Chain Validation

All system components must validate certificate chains:

1. **Root CA Verification:** Verify certificate chains to Vault PKI CA root
2. **Signature Validation:** Verify cryptographic signatures on all certificates
3. **Validity Period Check:** Ensure current time is within certificate validity period
4. **Revocation Status:** Check revocation status when revocation mechanism is implemented

**Implementation:**
- Python applications: Use `requests` library with system CA bundle (`/etc/ssl/certs/ca-certificates.crt`)
- Apache: Use `SSLVerifyDepth 3` for chain validation
- TLS connections: Validate server certificates against system trust store

### 4.2 Hostname Verification

All TLS connections must perform hostname verification:

- Verify certificate CN or SAN matches the hostname/IP being accessed
- Reject connections with hostname mismatches
- No hostname verification bypass in production

**Implementation:**
- Python `requests`: Default hostname verification enabled
- Browsers: Native hostname verification
- `curl`: Use `--cacert` instead of `-k` (insecure)

### 4.3 Acceptable Certificate Validation Failures

The following scenarios constitute certificate validation failures and must result in connection rejection:

- ❌ Expired certificate
- ❌ Certificate not yet valid
- ❌ Untrusted issuer (not in approved trust anchors)
- ❌ Invalid signature
- ❌ Hostname mismatch
- ❌ Self-signed certificate (unless explicitly trusted as root CA)
- ❌ Revoked certificate (when CRL/OCSP implemented)

---

## 5. Trust Anchor Management

### 5.1 Approved Trust Anchors

See **TRUST_ANCHORS.md** for complete list of approved trust anchors.

**Primary Trust Anchor:**
- **Vault PKI CA** (`pki_localhost`) - Internal certificate authority for all service certificates

**Secondary Trust Anchors:**
- **System CA Bundle** - Operating system provided CA certificates for external HTTPS connections

### 5.2 Trust Anchor Installation

Trust anchors are installed via automated scripts at container initialization:

**Installation Process:**
1. **Fetch CA Certificate:** Retrieve Vault PKI CA certificate from Vault KV store
2. **Write to Filesystem:** Save to `/usr/local/share/ca-certificates/vault_pki_ca.crt`
3. **Update Trust Store:** Run `update-ca-certificates` to add to system bundle
4. **Configure Applications:** Set `REQUESTS_CA_BUNDLE` environment variable

**Implementation:** `be_flask/scripts/install_ca.sh`

### 5.3 Trust Anchor Updates

Trust anchors may be updated in the following scenarios:

- **CA Certificate Renewal:** When Vault PKI root CA is renewed
- **Security Incident:** If CA private key is compromised
- **Policy Change:** If trust anchor approval is revoked

**Update Process:**
1. Deploy new CA certificate to Vault KV store
2. Restart affected containers to trigger CA installation
3. Verify all services validate certificates correctly
4. Document update in trust anchor registry

### 5.4 Trust Anchor Removal

Trust anchors are removed only when:

- CA is decommissioned
- Security policy mandates removal
- CA ceases to meet security requirements

**Removal Process:**
1. Remove CA certificate from trust anchor documentation
2. Delete CA certificate from system trust store
3. Update Vault configuration to disable CA
4. Verify applications reject certificates from removed CA

---

## 6. Certificate Lifecycle Management

### 6.1 Certificate Renewal

**Renewal Triggers:**
- **Time-based:** 30 days before expiration (renewal window opens)
- **Emergency:** Immediately upon security incident or key compromise

**Renewal Process:**
1. **Automated Renewal:** Services automatically request new certificates on restart
2. **Zero-Downtime:** New certificate issued before old certificate expires
3. **Rotation:** Private key regenerated with each renewal (no key reuse)

**Responsibility:**
- Automated services: Handle renewal transparently
- Manual certificates: Administrator initiates renewal

### 6.2 Certificate Revocation

**Note:** Certificate revocation mechanisms (CRL/OCSP) are not currently implemented. This is acceptable for MODERATE level in a development/internal environment.

**Planned Revocation Process (Future Enhancement):**
1. **Revocation Request:** Administrator submits request with justification
2. **Approval:** Security officer approves revocation
3. **Execution:** Certificate added to CRL via Vault CLI
4. **Notification:** Affected services notified to obtain new certificate
5. **Verification:** Confirm certificate is rejected by validation checks

**Revocation Reasons:**
- Private key compromise
- Service decommissioned
- Certificate misuse detected
- Policy violation

### 6.3 Key Compromise Response

If a private key is compromised:

1. **Immediate Actions:**
   - Revoke compromised certificate (when revocation implemented)
   - Disable affected service until new certificate issued
   - Investigate scope of compromise

2. **Recovery:**
   - Generate new key pair
   - Request new certificate with new public key
   - Update service configuration
   - Restart service with new certificate

3. **Post-Incident:**
   - Document incident and response
   - Review security controls
   - Update procedures if needed

### 6.4 Certificate Inventory

A certificate inventory must be maintained including:

- **Certificate Subject:** CN and SANs
- **Serial Number:** Unique identifier
- **Issuer:** CA that issued the certificate
- **Validity Period:** Not Before / Not After dates
- **Status:** Active, Expired, Revoked
- **Service/Owner:** Which service uses the certificate
- **Last Renewal:** Date of last renewal

**Maintenance:** Review inventory quarterly and update as certificates are issued/renewed/revoked.

---

## 7. Security Requirements

### 7.1 Private Key Protection

Private keys must be protected according to the following requirements:

**Storage:**
- ✅ Generated in-memory and never persisted to disk (Vault-issued certificates)
- ✅ Stored in tmpfs (in-memory filesystem) if temporary storage required
- ❌ Never stored on shared volumes or persistent storage
- ❌ Never transmitted over insecure channels

**Access Control:**
- File permissions: `600` (owner read/write only)
- No group or world access
- Root or service account ownership only

**Lifecycle:**
- Keys deleted when certificate expires
- Keys regenerated on renewal (no reuse)
- Keys destroyed on container termination

**Implementation:**
- Apache: Certificates stored in tmpfs volume (`/usr/local/apache2/conf/extra/certs`)
- Keycloak: Certificates stored in container filesystem (ephemeral)

### 7.2 Certificate Storage

Certificates (public keys) may be stored less restrictively:

- File permissions: `644` (world-readable acceptable)
- May be stored in persistent volumes if needed
- May be shared with monitoring/logging systems

### 7.3 Audit and Logging

The following events must be logged:

- ✅ Certificate issuance (Vault audit log)
- ✅ Authentication to Vault PKI (Vault audit log)
- ✅ Certificate validation failures (application logs)
- ⚠️ Certificate expiration warnings (manual monitoring currently)
- ⚠️ Certificate revocation (when implemented)

**Vault Audit Logging:**
- Enabled: `vault audit enable file file_path=/vault/logs/audit.log`
- Log location: `vault-infrastructure/logs/audit.log`
- Review: Monthly audit log review recommended

---

## 8. Operational Procedures

### 8.1 Initial PKI Setup

**Prerequisite:** Vault infrastructure must be initialized and unsealed.

**Setup Steps:**
1. Enable PKI secrets engine at `pki_localhost` path
2. Generate root CA or import external CA
3. Configure CA certificate and issuing URLs
4. Create certificate roles (apache-server-localhost, keycloak-server-localhost)
5. Create Vault policies for certificate issuance
6. Create AppRoles for automated certificate requests

**Documentation:** See `scripts/recreate/README_RECREATE.md` for detailed setup procedures.

### 8.2 Service Certificate Deployment

**Automated Process (Recommended):**

Services automatically obtain certificates on startup:

1. Container starts with Vault credentials (AppRole)
2. Initialization script (`entrypoint.sh`) authenticates to Vault
3. Script requests certificate from PKI role
4. Certificate and private key returned in JSON response
5. Script extracts and saves certificate files
6. Service starts with new certificates

**Manual Process (Exception Cases):**

```bash
# Authenticate to Vault
export VAULT_TOKEN=$(vault write -field=token auth/approle/login \
    role_id="$ROLE_ID" secret_id="$SECRET_ID")

# Request certificate
vault write -format=json pki_localhost/issue/apache-server-localhost \
    common_name="localhost" \
    alt_names="apache_fe,127.0.0.1" \
    ttl="2160h" \
    > certificate.json

# Extract files
jq -r '.data.certificate' certificate.json > cert.pem
jq -r '.data.private_key' certificate.json > key.pem
jq -r '.data.ca_chain[]' certificate.json > ca.pem

# Set permissions
chmod 644 cert.pem ca.pem
chmod 600 key.pem
```

### 8.3 Certificate Monitoring

**Current State:** Manual monitoring

**Recommended Monitoring:**
- Check certificate expiration dates monthly
- Alert 30 days before expiration
- Verify all services using current certificates

**Monitoring Commands:**
```bash
# Check certificate expiration
openssl x509 -in cert.pem -noout -enddate

# Check certificate in use by service
openssl s_client -connect localhost:443 -servername localhost | \
    openssl x509 -noout -dates

# List certificates issued by Vault PKI
vault list pki_localhost/certs
```

### 8.4 Emergency Procedures

**Certificate Expiration:**
1. Restart affected service to trigger automatic renewal
2. If automatic renewal fails, request certificate manually
3. Investigate and fix root cause of renewal failure

**CA Compromise:**
1. Immediately generate new root CA
2. Re-issue all certificates under new CA
3. Update trust anchors on all systems
4. Investigate compromise source

**Service Outage Due to Certificate Issue:**
1. Check certificate validity and expiration
2. Verify trust anchor installation
3. Check Vault availability
4. Review service logs for validation errors
5. Manually issue certificate if needed

---

## 9. Compliance and Governance

### 9.1 NIST 800-53 SC-17 Mapping

This certificate policy addresses NIST 800-53 SC-17 requirements:

| Requirement | Implementation | Evidence |
|-------------|----------------|----------|
| **SC-17.a** - Issue certificates under organization-defined policy | This document defines certificate policy | Certificate Policy (this document) |
| **SC-17.a** - Obtain certificates from approved provider | Vault PKI documented as approved provider | Section 2.1 (CA Information) |
| **SC-17.b** - Include only approved trust anchors | Trust anchors documented and controlled | TRUST_ANCHORS.md |
| **SC-17.b** - Manage trust stores | Automated trust store management | install_ca.sh script |

### 9.2 Policy Review and Updates

**Review Schedule:**
- **Routine Review:** Every 6 months
- **Triggered Review:** After security incidents, technology changes, or compliance updates

**Review Participants:**
- Security Officer (or Project Lead)
- System Administrator
- Compliance Officer (if applicable)

**Update Process:**
1. Review current policy against operational practices
2. Identify gaps or needed changes
3. Update policy document
4. Communicate changes to stakeholders
5. Update implementation if needed

### 9.3 Roles and Responsibilities

**Security Officer / Project Lead:**
- Approve certificate policy
- Approve trust anchor additions/removals
- Review certificate issuance for exceptions
- Conduct policy reviews

**System Administrator:**
- Implement PKI infrastructure
- Configure Vault PKI engine
- Maintain certificate inventory
- Respond to certificate incidents

**Developers:**
- Follow certificate policy in application development
- Implement proper certificate validation
- Report certificate-related issues

**Compliance Officer (if applicable):**
- Verify policy meets regulatory requirements
- Conduct compliance audits
- Document compliance evidence

---

## 10. Definitions and References

### 10.1 Definitions

- **Certificate Authority (CA):** Entity that issues digital certificates
- **Trust Anchor:** Authoritative source for which trust is assumed (root CA)
- **Certificate Chain:** Series of certificates from end-entity to root CA
- **Subject Alternative Name (SAN):** Additional identifiers in a certificate
- **Time To Live (TTL):** Validity period of a certificate
- **AppRole:** Vault authentication method for automated certificate requests

### 10.2 References

- **NIST SP 800-53 Rev 5:** Security and Privacy Controls for Information Systems
- **NIST SP 800-57:** Recommendation for Key Management
- **RFC 5280:** Internet X.509 Public Key Infrastructure Certificate and CRL Profile
- **HashiCorp Vault PKI Documentation:** https://developer.hashicorp.com/vault/docs/secrets/pki
- **CA/Browser Forum Baseline Requirements:** Industry standards for public CAs

### 10.3 Related Documents

- **TRUST_ANCHORS.md** - List of approved trust anchors
- **MOBILE_CODE_POLICY.md** - Security controls for JavaScript and web content
- **scripts/recreate/README_RECREATE.md** - PKI setup procedures
- **vault/policies/pki-policy.hcl** - Vault access control for PKI

---

## 11. Policy Approval

**Policy Owner:** DevSecOps Team  
**Approved By:** [Project Lead / Security Officer]  
**Approval Date:** December 12, 2025  
**Effective Date:** December 12, 2025  
**Next Review Date:** June 12, 2026

---

**Document History:**

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-12-12 | Initial certificate policy for NIST 800-53 SC-17 compliance | DevSecOps Team |

---

**Signatures:**

- [ ] Project Lead  
- [ ] Security Officer  
- [ ] Compliance Manager (if applicable)
