# Approved Trust Anchors

**NIST 800-53 SC-17.b Compliance Documentation**  
**Organization:** Local Cloud Project  
**Version:** 1.0  
**Last Updated:** December 12, 2025  
**Review Frequency:** Every 6 months  
**Next Review:** June 12, 2026

---

## Purpose

This document maintains the authoritative list of approved trust anchors (root certificates) for the Local Cloud system. Only trust anchors listed in this document may be included in system trust stores.

**NIST 800-53 SC-17.b Requirement:** "Include only approved trust anchors in trust stores or certificate stores managed by the organization."

---

## 1. Internal Trust Anchors

### 1.1 Vault PKI Certificate Authority

**Status:** ✅ **APPROVED**

#### Identification
- **CA Name:** Vault PKI CA
- **Certificate Path:** `pki_localhost` (Vault PKI secrets engine)
- **Common Name:** Vault PKI CA (configured during initialization)
- **Organization:** Local Cloud Project
- **CA Type:** Private/Internal Root Certificate Authority

#### Purpose and Scope
- **Primary Use:** Issue TLS/SSL certificates for internal services
- **Authorized For:**
  - Apache web server certificates
  - Keycloak IdP certificates
  - Backend service certificates
  - Internal service-to-service communication
- **Not Authorized For:**
  - Public-facing certificates requiring external trust
  - Certificates for services outside the Local Cloud ecosystem

#### Technical Details
- **Key Algorithm:** RSA
- **Key Size:** 2048 bits or greater
- **Signature Algorithm:** SHA-256 with RSA Encryption
- **Certificate Validity:** Configured at PKI initialization (typically 10 years for root CA)
- **Serial Number:** [Generated during PKI setup]

#### Trust Anchor Location
- **Vault Storage:** Accessible via `vault read pki_localhost/cert/ca`
- **Application Trust Store:** `/usr/local/share/ca-certificates/vault_pki_ca.crt`
- **System Trust Store:** `/etc/ssl/certs/ca-certificates.crt` (after `update-ca-certificates`)
- **Python Applications:** Referenced via `REQUESTS_CA_BUNDLE` environment variable

#### Installation Method
**Automated Installation:**
- **Script:** `be_flask/scripts/install_ca.sh`
- **Trigger:** Container startup (executed by entrypoint scripts)
- **Process:**
  1. Authenticate to Vault using AppRole credentials
  2. Retrieve CA certificate from Vault KV store (`secret/mes_local_cloud/app/flask`)
  3. Write CA certificate to `/usr/local/share/ca-certificates/vault_pki_ca.crt`
  4. Execute `update-ca-certificates` to add to system trust store
  5. Configure application environment variables (`REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`)

**Manual Installation (if needed):**
```bash
# Retrieve CA certificate from Vault
vault read -field=certificate pki_localhost/cert/ca > vault_pki_ca.crt

# Copy to system trust store location
sudo cp vault_pki_ca.crt /usr/local/share/ca-certificates/

# Update system trust store
sudo update-ca-certificates

# Verify installation
ls -l /etc/ssl/certs/ | grep vault_pki_ca
```

#### Approval Details
- **Approved By:** [Project Lead / Security Officer]
- **Approval Date:** December 12, 2025
- **Justification:** Required for internal PKI operations and secure service-to-service communication
- **Risk Assessment:** LOW - Internal use only, not exposed to external networks

#### Maintenance and Monitoring
- **Certificate Monitoring:** Check CA certificate expiration annually
- **Revocation:** Not applicable (root CA cannot be revoked; must be replaced)
- **Renewal Process:** If CA certificate nears expiration, generate new root CA and re-issue all certificates
- **Incident Response:** If CA private key compromised, immediately generate new CA and rotate all certificates

#### Dependencies
- **Services Relying on This CA:**
  - Apache frontend (`apache-fe` container)
  - Flask backend (`flask_be` container)
  - Keycloak server (`shared-keycloak-server` container)
  - All internal service-to-service HTTPS connections

#### Verification
**Verify Trust Anchor Installation:**
```bash
# Check if CA is in system trust store
grep -r "Vault PKI CA" /etc/ssl/certs/

# Verify Python trusts the CA
python3 -c "import ssl; print(ssl.get_default_verify_paths())"

# Test certificate validation
curl --cacert /usr/local/share/ca-certificates/vault_pki_ca.crt \
     https://shared_vault_server:8200/v1/sys/health
```

---

## 2. External Trust Anchors

### 2.1 Operating System CA Bundle

**Status:** ✅ **APPROVED** (Conditionally)

#### Identification
- **CA Bundle:** System Default Certificate Authorities
- **Location:** `/etc/ssl/certs/ca-certificates.crt` (Debian/Ubuntu)
- **Provider:** Operating system vendor (Debian/Ubuntu/Alpine)
- **Update Method:** OS package manager (`ca-certificates` package)

#### Purpose and Scope
- **Primary Use:** Validate external HTTPS connections (if needed)
- **Authorized For:**
  - Connections to external APIs or services requiring public CA trust
  - Package downloads over HTTPS (apt, pip, npm)
  - External monitoring or logging services
- **Current Usage:** Minimal (system uses primarily internal services)

#### Approval Conditions
- ✅ **Approved For:** Standard operating system-provided CAs
- ⚠️ **Conditional:** Only when connecting to external services
- ❌ **Not Approved For:** User-added custom CAs without review

#### Trust Anchor Management
- **Updates:** Automatic via OS package updates
- **Review:** Trust anchors in OS bundle trusted by default (Mozilla CA Program)
- **Customization:** Custom CAs require approval before addition

#### Included Certificate Authorities (Examples)
The OS CA bundle includes widely-trusted public CAs such as:
- DigiCert
- Let's Encrypt / ISRG
- GlobalSign
- IdenTrust
- Sectigo (formerly Comodo)
- And others from the Mozilla CA Certificate Program

**Note:** The complete list is maintained by the operating system and updated regularly.

#### Verification
```bash
# List all trusted CAs in system
awk -v cmd='openssl x509 -noout -subject' '/BEGIN/{close(cmd)};{print | cmd}' \
    < /etc/ssl/certs/ca-certificates.crt | grep "subject="

# Count trusted CAs
grep 'BEGIN CERTIFICATE' /etc/ssl/certs/ca-certificates.crt | wc -l

# Check package version
dpkg -l | grep ca-certificates
```

#### Approval Details
- **Approved By:** [Project Lead / Security Officer]
- **Approval Date:** December 12, 2025
- **Justification:** Required for external HTTPS connections and OS package management
- **Risk Assessment:** LOW - Standard OS-provided CAs, regularly updated

---

## 3. Trust Anchor Addition Process

### 3.1 Request for New Trust Anchor

To add a new trust anchor to the approved list:

1. **Submit Request:**
   - CA name and organization
   - Certificate file or source
   - Business justification
   - Services requiring the trust anchor
   - Risk assessment

2. **Security Review:**
   - Verify CA legitimacy and reputation
   - Review certificate technical details (key size, algorithms)
   - Assess security practices of CA operator
   - Evaluate necessity (can existing CAs be used?)

3. **Approval:**
   - Security officer or project lead approves
   - Document approval in this file
   - Update trust stores on all systems

4. **Implementation:**
   - Add CA certificate to appropriate trust stores
   - Update installation scripts if needed
   - Test certificate validation
   - Document in this registry

### 3.2 Trust Anchor Approval Criteria

A trust anchor must meet the following criteria for approval:

- ✅ **Legitimate Source:** CA operated by reputable organization
- ✅ **Strong Cryptography:** RSA ≥2048 bits or ECDSA ≥256 bits
- ✅ **Business Need:** Clear justification for requiring trust
- ✅ **Security Practices:** CA follows industry best practices (e.g., WebTrust audit)
- ✅ **Scope Limitation:** CA usage scope clearly defined
- ⚠️ **External CAs:** Prefer widely-recognized CAs over obscure ones
- ❌ **Self-Signed (External):** Self-signed certificates from external parties require exceptional justification

---

## 4. Trust Anchor Removal Process

### 4.1 Removal Triggers

A trust anchor may be removed if:

- ❌ CA ceases operations or is no longer maintained
- ❌ CA suffers security compromise (private key breach)
- ❌ CA no longer meets security requirements
- ❌ CA is no longer needed for business operations
- ❌ CA is found to have issued fraudulent certificates

### 4.2 Removal Procedure

1. **Identify Impact:**
   - List all services using certificates from this CA
   - Assess service disruption risk

2. **Plan Migration:**
   - Obtain replacement certificates from approved CA
   - Schedule migration window
   - Notify stakeholders

3. **Execute Removal:**
   - Remove CA certificate from trust stores
   - Update installation scripts
   - Restart affected services
   - Verify replacement certificates work

4. **Document:**
   - Update this document with removal
   - Archive removed CA information
   - Document lessons learned

---

## 5. Trust Store Management

### 5.1 System Trust Store Locations

| System Component | Trust Store Location | Management Method |
|------------------|----------------------|-------------------|
| **Debian/Ubuntu OS** | `/etc/ssl/certs/ca-certificates.crt` | `update-ca-certificates` |
| **Python (requests)** | `REQUESTS_CA_BUNDLE` environment variable | Application configuration |
| **Python (system)** | `/etc/ssl/certs/ca-certificates.crt` | `ssl` module default |
| **Apache** | `SSLCACertificateFile` directive | Apache configuration |
| **Keycloak** | Java trust store or `VAULT_CACERT` | Keycloak configuration |
| **Docker** | Host system trust store (inherited) | Container configuration |

### 5.2 Trust Store Update Procedures

**Adding Trust Anchor:**
```bash
# Copy CA certificate to ca-certificates directory
sudo cp new-ca.crt /usr/local/share/ca-certificates/

# Update system trust store
sudo update-ca-certificates

# Verify addition
sudo update-ca-certificates --verbose | grep new-ca
```

**Removing Trust Anchor:**
```bash
# Remove CA certificate file
sudo rm /usr/local/share/ca-certificates/trust-anchor.crt

# Update system trust store
sudo update-ca-certificates --fresh

# Verify removal
! grep -q "Trust Anchor" /etc/ssl/certs/ca-certificates.crt
```

**Automated Updates (via install_ca.sh):**
- Trust anchors automatically updated on container startup
- Vault PKI CA fetched from Vault and installed
- No manual intervention required for standard operations

### 5.3 Trust Store Auditing

**Quarterly Review:**
- List all trust anchors in system trust stores
- Verify each trust anchor is approved in this document
- Remove any unapproved trust anchors
- Update this document if needed

**Audit Commands:**
```bash
# List all CA certificates in system trust store
awk -v cmd='openssl x509 -noout -subject -fingerprint' \
    '/BEGIN/{close(cmd)};{print | cmd}' \
    < /etc/ssl/certs/ca-certificates.crt

# Compare against approved list
diff <(approved_cas.txt) <(installed_cas.txt)
```

---

## 6. Trust Anchor Security

### 6.1 CA Private Key Protection

**Critical Requirement:** CA private keys must be protected with highest security:

- ✅ **Vault PKI CA:** Private key stored encrypted in Vault backend
- ✅ **Access Control:** Only Vault root or admin tokens can access CA key
- ✅ **Audit Logging:** All CA key operations logged in Vault audit log
- ❌ **Never Export:** CA private keys should never be exported from Vault
- ❌ **No Backups:** If backing up Vault data, ensure encryption at rest

**Vault CA Key Security:**
- Key generated within Vault (never imported)
- Vault seal protects keys at rest (AES-256-GCM)
- Unseal keys required to access (Shamir secret sharing)
- HSM integration possible for production (future enhancement)

### 6.2 Trust Anchor Distribution Security

When distributing CA certificates (public keys only):

- ✅ Use authenticated channels (HTTPS with verified certificate)
- ✅ Verify CA certificate fingerprint after retrieval
- ✅ Use automation to prevent manual errors
- ⚠️ Document distribution method
- ❌ Never distribute CA private keys

**Distribution Method:**
- Vault KV store → Authenticated retrieval via AppRole
- Integrity verified through Vault's cryptographic guarantees
- Automatic installation via install_ca.sh script

---

## 7. Compliance and Monitoring

### 7.1 NIST 800-53 SC-17.b Compliance

This document satisfies NIST 800-53 SC-17.b requirements:

| Requirement | Implementation | Evidence |
|-------------|----------------|----------|
| **Approved Trust Anchors Only** | All trust anchors documented and approved | This document |
| **Trust Store Management** | Automated installation and verification | install_ca.sh script |
| **Trust Anchor Review** | 6-month review cycle | Review schedule above |
| **Removal Process** | Documented procedure | Section 4 |

### 7.2 Trust Anchor Monitoring

**Monthly Checks:**
- Verify Vault PKI CA certificate validity
- Check for CA certificate expiration warnings
- Review Vault audit logs for unusual CA operations

**Quarterly Checks:**
- Full trust store audit against this document
- Review trust anchor additions/removals
- Update this document if needed

**Annual Checks:**
- Comprehensive trust anchor security review
- Evaluate new CA technologies or options
- Update trust anchor policy if needed

---

## 8. References

### 8.1 Related Documents
- **CERTIFICATE_POLICY.md** - Complete certificate management policy
- **vault/policies/pki-policy.hcl** - Vault access control for PKI operations
- **be_flask/scripts/install_ca.sh** - Trust anchor installation script
- **scripts/recreate/README_RECREATE.md** - PKI setup procedures

### 8.2 Standards and Guidelines
- **NIST SP 800-53 Rev 5:** SC-17 Public Key Infrastructure Certificates
- **NIST SP 800-57:** Recommendation for Key Management
- **RFC 5280:** Internet X.509 PKI Certificate and CRL Profile
- **Mozilla CA Certificate Program:** https://wiki.mozilla.org/CA

---

## 9. Document Maintenance

### 9.1 Review Schedule
- **Frequency:** Every 6 months
- **Next Review:** June 12, 2026
- **Responsibility:** Security Officer / Project Lead

### 9.2 Update Triggers
- Addition or removal of trust anchors
- Security incidents involving CAs
- Changes to trust store management procedures
- Compliance requirement changes

### 9.3 Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-12-12 | Initial trust anchor documentation for NIST 800-53 SC-17 compliance | DevSecOps Team |

---

## 10. Approval

**Document Owner:** DevSecOps Team  
**Approved By:** [Project Lead / Security Officer]  
**Approval Date:** December 12, 2025  
**Effective Date:** December 12, 2025  
**Next Review:** June 12, 2026

---

**Signatures:**

- [ ] Project Lead  
- [ ] Security Officer  
- [ ] System Administrator

---

## Appendix A: Current Trust Anchor Inventory

**As of:** December 12, 2025

| Trust Anchor | Type | Status | Approval Date | Next Review |
|--------------|------|--------|---------------|-------------|
| Vault PKI CA (`pki_localhost`) | Internal Root CA | ✅ Active | 2025-12-12 | 2026-06-12 |
| OS CA Bundle | Public CAs | ✅ Active | 2025-12-12 | 2026-06-12 |

**Total Approved Trust Anchors:** 2  
**Pending Approvals:** 0  
**Recently Removed:** 0
