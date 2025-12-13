# Cryptographic Protection Policy

**NIST 800-53 SC-13 Compliance Documentation**  
**Organization:** Local Cloud Project  
**Version:** 1.0  
**Last Updated:** December 13, 2025  
**Compliance Level:** MODERATE  
**Next Review:** June 13, 2026

---

## Executive Summary

This document defines the cryptographic uses and implementations for the Local Cloud system in accordance with NIST 800-53 SC-13 (Cryptographic Protection) at the MODERATE security categorization level. All cryptographic implementations use industry-standard, NIST-approved algorithms and key sizes.

**Compliance Status:** ✅ **COMPLIANT at MODERATE level**

---

## 1. Cryptographic Uses (SC-13a)

The Local Cloud system employs cryptography for the following organization-defined uses:

### 1.1 Transport Layer Security (TLS/HTTPS)
**Purpose:** Protect data in transit between clients and servers  
**Components:** Apache web server, Keycloak IdP, Vault API, Flask backend  
**Security Objective:** Confidentiality and integrity of transmitted data

### 1.2 Digital Signatures
**Purpose:** Authenticate JWT tokens and verify identity assertions  
**Components:** Keycloak JWT tokens, certificate signatures  
**Security Objective:** Authentication and non-repudiation

### 1.3 Password Hashing
**Purpose:** Protect user credentials stored in database  
**Components:** PostgreSQL user authentication table  
**Security Objective:** Confidentiality of authentication credentials

### 1.4 Random Number Generation
**Purpose:** Generate cryptographic keys, secrets, and session tokens  
**Components:** OpenSSL, Python secrets module, Vault  
**Security Objective:** Unpredictability of cryptographic material

### 1.5 Data Encryption at Rest
**Purpose:** Protect sensitive data stored on disk  
**Components:** Vault storage backend, database encryption (optional)  
**Security Objective:** Confidentiality of stored data

### 1.6 Public Key Infrastructure (PKI)
**Purpose:** Issue and validate X.509 certificates for service authentication  
**Components:** Vault PKI engine, Apache TLS certificates, Keycloak certificates  
**Security Objective:** Authentication and secure key establishment

---

## 2. Cryptographic Implementations (SC-13b)

### 2.1 TLS/HTTPS Implementation

#### **Apache Web Server (Frontend)**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Protocol Version** | TLS 1.3 only | NIST SP 800-52 Rev. 2 |
| **Cipher Suites** | Modern Mozilla configuration | FIPS 140-2 compatible |
| **Certificate Type** | RSA 2048-bit | NIST SP 800-57 |
| **Signature Algorithm** | SHA-256 with RSA | FIPS 180-4 |
| **Key Exchange** | X25519, P-256, P-384 | NIST SP 800-56A |
| **HTTP Strict Transport Security** | max-age=63072000 (2 years) | RFC 6797 |
| **OCSP Stapling** | Enabled | RFC 6960 |

**Configuration File:** [apache/config/ssl/apache_ssl.conf](../apache/config/ssl/apache_ssl.conf)

**Cipher Configuration:**
```apache
SSLProtocol             -all +TLSv1.3
SSLOpenSSLConfCmd       Curves X25519:prime256v1:secp384r1
SSLHonorCipherOrder     off
SSLSessionTickets       off
```

**Certificate Source:** Vault PKI engine (`pki_localhost/roles/apache-server-localhost`)

#### **Vault Server (Secrets Management)**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Protocol Version** | TLS 1.3 minimum | NIST SP 800-52 Rev. 2 |
| **Certificate Type** | RSA 2048-bit | NIST SP 800-57 |
| **Signature Algorithm** | SHA-256 with RSA | FIPS 180-4 |
| **Storage Encryption** | AES-256-GCM | NIST SP 800-38D |

**Configuration File:** [vault-infrastructure/config/vault-config.hcl](../../vault-infrastructure/config/vault-config.hcl)

**TLS Configuration:**
```hcl
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 0
  tls_cert_file = "/vault/certs/vault-cert.pem"
  tls_key_file = "/vault/certs/vault-key.pem"
  tls_min_version = "tls13"
}
```

**Storage Encryption:** Vault automatically encrypts all data at rest using AES-256-GCM with a master key derived from unseal keys.

#### **Keycloak Identity Provider**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Protocol Version** | TLS 1.3 | NIST SP 800-52 Rev. 2 |
| **Certificate Type** | RSA 2048-bit | NIST SP 800-57 |
| **Signature Algorithm** | SHA-256 with RSA | FIPS 180-4 |
| **HTTP Strict Transport Security** | Enabled via proxy | RFC 6797 |

**Configuration File:** [keycloak-infrastructure/config/keycloak.conf](../../keycloak-infrastructure/config/keycloak.conf)

**Certificate Source:** Vault PKI engine (`pki_localhost/roles/keycloak-server-localhost`)

---

### 2.2 Digital Signature Implementation

#### **JWT Token Signatures (Keycloak)**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Algorithm** | RS256 (RSA-SHA256) | RFC 7518 |
| **Key Type** | RSA | FIPS 186-4 |
| **Key Size** | 2048 bits minimum | NIST SP 800-57 |
| **Hash Algorithm** | SHA-256 | FIPS 180-4 |

**Implementation Location:** [be_flask/src/keycloak_auth.py](../be_flask/src/keycloak_auth.py)

**Token Verification:**
```python
from jwt.algorithms import RSAAlgorithm

payload = jwt.decode(
    token,
    public_key,
    algorithms=['RS256'],
    options={
        'verify_signature': True,
        'verify_exp': True
    }
)
```

**Public Key Retrieval:** JWKS endpoint at `{keycloak_url}/realms/{realm}/protocol/openid-connect/certs`

#### **X.509 Certificate Signatures**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Signature Algorithm** | SHA-256 with RSA | NIST SP 800-57 |
| **Certificate Authority** | Vault PKI CA | Internal CA |
| **Key Size** | 2048 bits minimum | NIST SP 800-57 |

**PKI Configuration:** [keycloak-infrastructure/scripts/setup-shared-pki-role.sh](../../keycloak-infrastructure/scripts/setup-shared-pki-role.sh)

---

### 2.3 Password Hashing Implementation

#### **User Password Storage**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Algorithm** | Werkzeug PBKDF2-HMAC-SHA256 | NIST SP 800-132 |
| **Iterations** | 260,000 (default) | OWASP recommendation 2023 |
| **Salt Size** | 16 bytes | NIST SP 800-132 |
| **Output Size** | 32 bytes (256 bits) | NIST SP 800-132 |

**Implementation Location:** [vault/scripts/setup-vault-app.sh](../vault/scripts/setup-vault-app.sh#L203)

**Password Hashing:**
```bash
generate_password_hash() {
    local password="$1"
    echo "$password" | docker run --rm -i python:3.10-slim sh -c \
        "pip install -q werkzeug && python3 -c \
        \"from werkzeug.security import generate_password_hash; \
        import sys; \
        print(generate_password_hash(sys.stdin.read().strip()), end='')\""
}
```

**Python Library:** `werkzeug.security.generate_password_hash` (Flask-compatible, PBKDF2-HMAC-SHA256)

**Note:** Keycloak manages its own user passwords independently using bcrypt with adaptive hashing.

---

### 2.4 Random Number Generation

#### **Cryptographic Random Values**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Source** | OpenSSL `rand` command | NIST SP 800-90A |
| **Entropy Source** | OS kernel (/dev/urandom) | NIST SP 800-90B |
| **Output Encoding** | Base64 | RFC 4648 |

**Implementation Locations:**
- [keycloak-infrastructure/scripts/store-secrets-in-vault.sh](../../keycloak-infrastructure/scripts/store-secrets-in-vault.sh#L78-L79)
- [vault/scripts/setup-vault-app.sh](../vault/scripts/setup-vault-app.sh#L151)

**Secret Generation Examples:**
```bash
# JWT secret key (256 bits)
JWT_SECRET=$(openssl rand -base64 32)

# Database password (256 bits)
KEYCLOAK_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# MinIO application password (256 bits)
MINIO_APP_PASSWORD=$(openssl rand -base64 32)
```

**Python Random Generation:** `secrets` module (CSPRNG)
```python
import secrets
token = secrets.token_urlsafe(32)  # 256 bits of entropy
```

---

### 2.5 Data Encryption at Rest

#### **Vault Storage Encryption**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Algorithm** | AES-256-GCM | NIST SP 800-38D |
| **Key Size** | 256 bits | NIST SP 800-57 |
| **Key Derivation** | Shamir Secret Sharing (5 shares, 3 threshold) | NIST SP 800-108 |
| **Initialization Vector** | 96 bits (unique per encryption) | NIST SP 800-38D |

**Implementation:** HashiCorp Vault automatically encrypts all data written to the storage backend using AES-256-GCM. The encryption key is protected by Shamir's Secret Sharing algorithm, requiring 3 of 5 unseal keys to reconstruct the master key.

**Configuration:** [vault-infrastructure/docker-compose.yaml](../../vault-infrastructure/docker-compose.yaml#L71-L74)

**Optional OS-Level Encryption:**
```yaml
# SC-28 Compliance: Vault encrypts internally (AES-256-GCM) but OS-level encryption adds defense-in-depth
# Setup: Create encrypted volume with BitLocker (Windows) or LUKS (Linux)
# Set ENCRYPTED_VOLUME_PATH env var to encrypted directory path
device: ${ENCRYPTED_VOLUME_PATH:-./vault_data_unencrypted}
```

#### **PostgreSQL Database Encryption**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **Transport Encryption** | TLS 1.3 (optional) | NIST SP 800-52 Rev. 2 |
| **Storage Encryption** | OS-level volume encryption | BitLocker/LUKS/dm-crypt |
| **Password Hashing** | Scram-SHA-256 (PostgreSQL default) | RFC 7677 |

**Note:** PostgreSQL 14 supports TLS for client connections and scram-sha-256 for password authentication. At-rest encryption is achieved via OS-level volume encryption (BitLocker on Windows, LUKS on Linux).

---

### 2.6 Public Key Infrastructure (PKI)

#### **Vault PKI Engine**
| Parameter | Implementation | Standard |
|-----------|---------------|----------|
| **CA Key Type** | RSA | FIPS 186-4 |
| **CA Key Size** | 2048 bits minimum | NIST SP 800-57 |
| **Certificate Key Type** | RSA | FIPS 186-4 |
| **Certificate Key Size** | 2048 bits | NIST SP 800-57 |
| **Signature Algorithm** | SHA-256 with RSA | FIPS 180-4 |
| **Certificate Validity** | 90 days default, 1 year max | Industry best practice |

**PKI Roles:**
- `apache-server-localhost` - Apache web server certificates
- `keycloak-server-localhost` - Keycloak IdP certificates

**Configuration Files:**
- [keycloak-infrastructure/scripts/setup-shared-pki-role.sh](../../keycloak-infrastructure/scripts/setup-shared-pki-role.sh)
- [vault/scripts/setup-vault-app.sh](../vault/scripts/setup-vault-app.sh)

**Certificate Policy:** See [CERTIFICATE_POLICY.md](CERTIFICATE_POLICY.md) for comprehensive PKI requirements.

---

## 3. Cryptographic Libraries and Software

### 3.1 OpenSSL
**Version:** 3.x (Alpine Linux), 3.4.0+ (Apache container)  
**FIPS Status:** OpenSSL 3.x supports FIPS 140-3 validated cryptographic module  
**Usage:** TLS/SSL, certificate generation, random number generation, hashing  
**Standard:** FIPS 140-2/140-3 validated (when FIPS module enabled)

**Verification:**
```bash
# Check OpenSSL version
openssl version

# Check available algorithms
openssl list -digest-algorithms
openssl list -cipher-algorithms
```

### 3.2 Python Cryptography Libraries
**Libraries:**
- `cryptography>=41.0.0` - Low-level cryptographic primitives (FIPS 140-2 backend available)
- `PyJWT>=2.8.0` - JWT token verification (RS256 support)
- `werkzeug>=2.0` - Password hashing (PBKDF2-HMAC-SHA256)
- `hvac>=1.2.1` - Vault client library

**FIPS Status:** Python `cryptography` library can use OpenSSL FIPS module as backend

**Requirements File:** [be_flask/requirements.txt](../be_flask/requirements.txt)

### 3.3 HashiCorp Vault
**Version:** 1.21  
**FIPS Status:** Vault Enterprise supports FIPS 140-2 mode (not enabled in OSS version)  
**Usage:** PKI certificate issuance, secrets encryption, key management  
**Cryptography:** AES-256-GCM for storage, RSA-2048 for PKI, SHA-256 for hashing

**Image:** `hashicorp/vault:1.21`

### 3.4 PostgreSQL
**Version:** 14-alpine  
**FIPS Status:** PostgreSQL can use OpenSSL FIPS module  
**Usage:** Password hashing (scram-sha-256), optional TLS for connections  
**Cryptography:** SCRAM-SHA-256 for authentication, AES for TLS

**Image:** `postgres:14-alpine`

### 3.5 Apache HTTP Server
**Version:** 2.4.60+  
**FIPS Status:** mod_ssl can use OpenSSL FIPS module  
**Usage:** TLS/SSL termination, HTTPS encryption  
**Cryptography:** TLS 1.3, X25519/P-256/P-384 key exchange, AEAD cipher suites

**Image:** `httpd:alpine`

---

## 4. FIPS 140-2 Compliance Assessment

### 4.1 Current Status

**Compliance Level:** **MODERATE (Non-FIPS Mode)**

The system uses FIPS-approved cryptographic algorithms and key sizes, meeting NIST 800-53 SC-13 requirements at the MODERATE level. However, FIPS 140-2 **validated** cryptographic modules are not explicitly enabled.

### 4.2 FIPS-Approved Algorithms in Use

✅ **Transport Encryption:**
- TLS 1.3 with ECDHE (X25519, P-256, P-384) - NIST SP 800-56A
- AES-GCM cipher suites - FIPS 197, SP 800-38D

✅ **Digital Signatures:**
- RSA-2048 with SHA-256 - FIPS 186-4, FIPS 180-4
- ECDSA (supported, not currently used) - FIPS 186-4

✅ **Hashing:**
- SHA-256, SHA-384, SHA-512 - FIPS 180-4
- HMAC-SHA256 - FIPS 198-1

✅ **Key Derivation:**
- PBKDF2-HMAC-SHA256 - NIST SP 800-132
- SCRAM-SHA-256 - RFC 7677

✅ **Symmetric Encryption:**
- AES-256-GCM (Vault storage) - FIPS 197, SP 800-38D

✅ **Random Number Generation:**
- OpenSSL DRBG (Deterministic Random Bit Generator) - NIST SP 800-90A

### 4.3 Upgrade Path to FIPS 140-2 Validated Cryptography

To achieve **FIPS 140-2 validation** (required for HIGH impact systems):

#### **Step 1: Enable OpenSSL FIPS Module**
**Difficulty:** 🟡 **MODERATE**  
**Effort:** 2-4 hours

**Actions:**
1. Use FIPS-enabled base images (e.g., `redhat/ubi8-minimal` with OpenSSL FIPS module)
2. Enable FIPS mode in OpenSSL configuration
3. Verify FIPS mode: `openssl version` should show "fips"

**Impact:** Requires rebuilding all Docker images with FIPS-enabled OpenSSL

#### **Step 2: Enable Python Cryptography FIPS Mode**
**Difficulty:** 🟡 **MODERATE**  
**Effort:** 1-2 hours

**Actions:**
1. Install Python `cryptography` library with FIPS support
2. Set environment variable: `OPENSSL_FIPS=1`
3. Verify FIPS backend is active

**Impact:** Python applications automatically use OpenSSL FIPS module

#### **Step 3: Upgrade to Vault Enterprise with FIPS 140-2**
**Difficulty:** 🔴 **DIFFICULT** (requires license)  
**Effort:** 4-8 hours + licensing

**Actions:**
1. Obtain HashiCorp Vault Enterprise license
2. Enable FIPS 140-2 mode in Vault configuration
3. Migrate data from OSS to Enterprise version

**Impact:** Vault Enterprise provides FIPS 140-2 validated cryptography for storage encryption and PKI operations

**Cost:** Vault Enterprise license required ($$$$)

#### **Step 4: PostgreSQL FIPS Mode**
**Difficulty:** 🟢 **EASY**  
**Effort:** 1 hour

**Actions:**
1. Use FIPS-enabled OpenSSL for PostgreSQL TLS connections
2. Verify TLS connections use FIPS-approved cipher suites

**Impact:** Minimal - PostgreSQL inherits FIPS mode from OpenSSL

---

## 5. Key Size Requirements

### 5.1 Current Key Sizes (NIST SP 800-57 Compliant)

| Algorithm | Current Size | NIST Minimum | Security Strength | Valid Until |
|-----------|-------------|--------------|-------------------|-------------|
| **RSA** | 2048 bits | 2048 bits | 112 bits | 2030 |
| **ECC (ECDSA)** | P-256 (256 bits) | 224 bits | 128 bits | Beyond 2031 |
| **AES** | 256 bits | 128 bits | 256 bits | Beyond 2031 |
| **SHA-2** | 256 bits | 224 bits | 128 bits | Beyond 2031 |

**Source:** NIST SP 800-57 Part 1 Rev. 5 (Table 4: Recommended Algorithms and Key Sizes)

### 5.2 Key Rotation Schedule

| Key Type | Rotation Frequency | Current Implementation |
|----------|-------------------|------------------------|
| **TLS Server Certificates** | 90 days | ✅ Vault PKI auto-rotation |
| **JWT Signing Keys** | 1 year | ⚠️ Manual rotation (Keycloak) |
| **Vault Master Key** | Never (protected by Shamir) | ✅ Unsealed with 3/5 keys |
| **Database Passwords** | 90 days | ⚠️ Manual rotation via Vault |
| **MinIO Access Keys** | 90 days | ⚠️ Manual rotation via Vault |

**Recommendation:** Implement automated key rotation for JWT signing keys and database credentials using Vault's dynamic secrets feature.

---

## 6. Cryptographic Standards Compliance Matrix

| Standard | Requirement | Compliance Status | Implementation |
|----------|-------------|-------------------|----------------|
| **NIST SP 800-52 Rev. 2** | TLS 1.2+ for federal systems | ✅ **TLS 1.3** | Apache, Vault, Keycloak |
| **NIST SP 800-57 Part 1** | 2048-bit RSA minimum | ✅ **2048-bit RSA** | All certificates |
| **NIST SP 800-132** | PBKDF2 for password storage | ✅ **PBKDF2-HMAC-SHA256** | Werkzeug library |
| **NIST SP 800-38D** | AES-GCM for authenticated encryption | ✅ **AES-256-GCM** | Vault storage |
| **NIST SP 800-90A** | DRBG for random number generation | ✅ **OpenSSL DRBG** | OpenSSL `rand` |
| **FIPS 140-2** | Validated cryptographic modules | ⚠️ **Algorithms approved, modules not validated** | Use approved algorithms |
| **FIPS 180-4** | SHA-256+ for hashing | ✅ **SHA-256, SHA-384** | All hash operations |
| **FIPS 186-4** | RSA/ECDSA for digital signatures | ✅ **RSA-2048, ECDSA P-256** | JWT, certificates |
| **FIPS 197** | AES for encryption | ✅ **AES-256** | Vault, TLS |
| **RFC 7518** | JWS algorithms | ✅ **RS256** | Keycloak JWT |

---

## 7. Prohibited Cryptographic Algorithms

The following cryptographic algorithms are **PROHIBITED** due to known vulnerabilities:

❌ **DES / 3DES** - Inadequate key size, vulnerable to brute force  
❌ **MD5** - Collision attacks demonstrated  
❌ **SHA-1** - Collision attacks demonstrated (deprecated by NIST)  
❌ **RC4** - Stream cipher biases  
❌ **Blowfish** - 64-bit block size (vulnerable to birthday attacks)  
❌ **RSA < 2048 bits** - Insufficient security strength  
❌ **TLS 1.0 / TLS 1.1** - Protocol vulnerabilities (deprecated by IETF)  
❌ **SSL v2 / SSL v3** - Multiple protocol vulnerabilities

**Enforcement:** All TLS configurations explicitly disable weak protocols and ciphers.

---

## 8. Compliance Verification Procedures

### 8.1 TLS Configuration Testing

**Test TLS 1.3 Enforcement:**
```bash
# Verify TLS 1.3 is used
openssl s_client -connect localhost:443 -tls1_3

# Verify TLS 1.2 is rejected
openssl s_client -connect localhost:443 -tls1_2 
# Expected: handshake failure

# Check cipher suites
nmap --script ssl-enum-ciphers -p 443 localhost
```

### 8.2 Certificate Validation

**Verify RSA-2048 Certificates:**
```bash
# Check certificate key size
openssl x509 -in certificate.pem -text -noout | grep "Public-Key"
# Expected: Public-Key: (2048 bit)

# Check signature algorithm
openssl x509 -in certificate.pem -text -noout | grep "Signature Algorithm"
# Expected: Signature Algorithm: sha256WithRSAEncryption
```

### 8.3 Password Hash Strength

**Verify PBKDF2 Parameters:**
```bash
# Check database for password hashes
docker exec postgres_db psql -U admin -d postgres_db -c \
  "SELECT username, LEFT(password, 30) FROM users LIMIT 1;"

# Expected format: pbkdf2:sha256:260000$...
```

### 8.4 Vault Encryption Verification

**Check Vault Storage Encryption:**
```bash
# Seal Vault and check sealed status
docker exec shared_vault_server vault status
# Expected: Sealed: true

# Data should be encrypted in storage
docker exec shared_vault_server cat /vault/file/sys/token/id/...
# Expected: Binary encrypted data (not readable)
```

---

## 9. Exceptions and Deviations

### 9.1 Development Environment

**Exception:** TLS certificate validation may be disabled in development environments for local testing.

**Justification:** Self-signed certificates are used for localhost development. Production deployments MUST enable certificate validation.

**Affected Components:**
- `VAULT_SKIP_VERIFY=1` (development only)
- `KEYCLOAK_SKIP_VERIFY=True` (development only)

**Mitigation:** Environment variables enforce strict validation in production.

### 9.2 FIPS 140-2 Validation

**Exception:** FIPS 140-2 **validated** cryptographic modules are not enabled (MODERATE level accepts FIPS-approved algorithms).

**Justification:** MODERATE impact systems may use FIPS-approved algorithms without formal validation. FIPS validation is required for HIGH impact systems.

**Mitigation:** All algorithms and key sizes meet NIST recommendations. Upgrade path documented in Section 4.3.

---

## 10. Responsibilities

| Role | Responsibility |
|------|---------------|
| **System Administrator** | Configure TLS settings, manage certificates, enable FIPS mode |
| **Security Officer** | Review cryptographic policy, approve algorithm changes, audit compliance |
| **DevOps Engineer** | Deploy Vault PKI, rotate certificates, monitor expiration |
| **Application Developer** | Use approved libraries, implement secure key storage, follow coding standards |

---

## 11. Review and Update Schedule

- **Policy Review:** Annually (next review: December 13, 2026)
- **Algorithm Review:** Every 2 years or upon NIST guidance updates
- **Certificate Rotation:** 90 days (automated via Vault PKI)
- **Key Material Audit:** Quarterly

---

## 12. References

1. **NIST SP 800-52 Rev. 2** - Guidelines for the Selection, Configuration, and Use of TLS
2. **NIST SP 800-57 Part 1 Rev. 5** - Recommendation for Key Management
3. **NIST SP 800-132** - Recommendation for Password-Based Key Derivation
4. **NIST SP 800-38D** - Recommendation for Block Cipher Modes of Operation: GCM
5. **NIST SP 800-90A** - Recommendation for Random Number Generation Using Deterministic RBGs
6. **NIST FIPS 140-2** - Security Requirements for Cryptographic Modules
7. **NIST FIPS 180-4** - Secure Hash Standard (SHS)
8. **NIST FIPS 186-4** - Digital Signature Standard (DSS)
9. **NIST FIPS 197** - Advanced Encryption Standard (AES)
10. **RFC 7518** - JSON Web Algorithms (JWA)
11. **RFC 6797** - HTTP Strict Transport Security (HSTS)
12. **Mozilla TLS Configuration Generator** - https://ssl-config.mozilla.org/

---

## Document Control

**Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-13 | System Administrator | Initial policy creation for SC-13 compliance |

**Approval:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Security Officer | ___________________ | ___________________ | __________ |
| System Administrator | ___________________ | ___________________ | __________ |

---

**END OF DOCUMENT**
