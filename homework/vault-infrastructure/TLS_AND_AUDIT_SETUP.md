# Enabling TLS and Audit Logging on Vault

This guide explains how to enable TLS encryption and audit logging on the shared Vault infrastructure.

## Overview

- **TLS Configuration**: Must be done via configuration files (cannot be done from UI)
- **Audit Logging**: Can be enabled via UI, CLI, or API after Vault is initialized

## Quick Setup Steps

### 1. Generate TLS Certificates

```bash
cd homework/vault-infrastructure/scripts
./generate-vault-certs.sh
```

This creates self-signed certificates in `homework/vault-infrastructure/certs/`:
- `vault-cert.pem` - TLS certificate
- `vault-key.pem` - Private key

### 2. Restart Vault with TLS Enabled

```bash
cd homework/vault-infrastructure
docker compose down
docker compose up -d
```

Vault will now use HTTPS on port 8200.

### 3. Unseal Vault

```bash
cd scripts
./unseal-vault.sh
```

### 4. Enable Audit Logging

**Option A: Using the provided script (Recommended)**
```bash
cd scripts
./enable-audit-logging.sh
```

**Option B: Using Vault CLI**
```bash
docker exec -e VAULT_TOKEN="<your-root-token>" -e VAULT_SKIP_VERIFY=1 shared_vault_server \
  vault audit enable file file_path=/vault/logs/audit.log
```

### 5. Verify Configuration

Check TLS is working:
```bash
curl -k https://localhost:8200/v1/sys/health
```

Check audit logging is enabled:
```bash
docker exec -e VAULT_TOKEN="<your-root-token>" -e VAULT_SKIP_VERIFY=1 shared_vault_server \
  vault audit list
```

View audit logs in real-time:
```bash
cd homework/vault-infrastructure
tail -f logs/audit.log
```

View formatted audit logs:
```bash
cat logs/audit.log | jq
```

## Important Notes

### Self-Signed Certificates

The generated certificates are **self-signed** and suitable for development/testing only.

**For production:**
- Use certificates from a trusted Certificate Authority (Let's Encrypt, DigiCert, etc.)
- Properly configure certificate validation
- Remove `VAULT_SKIP_VERIFY=1` environment variable


### Client Configuration

Applications connecting to Vault need to be updated:

**For 4_LDAP_XACML application:**

Update `.env` file:
```bash
VAULT_ADDR=https://shared_vault_server:8200
```

Update application to skip TLS verification (development only):
```python
# In vault_client.py or environment
os.environ['VAULT_SKIP_VERIFY'] = '1'
```

Or configure proper CA certificate validation for production.

## Disabling Audit Logging

If needed:
```bash
docker exec -e VAULT_TOKEN="<root-token>" -e VAULT_SKIP_VERIFY=1 shared_vault_server \
  vault audit disable file/
```

## Troubleshooting

### "Connection refused" errors

Ensure you're using HTTPS:
```bash
export VAULT_ADDR=https://localhost:8200
export VAULT_SKIP_VERIFY=1
```

### Certificate errors

For development, skip verification:
```bash
export VAULT_SKIP_VERIFY=1
curl -k https://localhost:8200/v1/sys/health
```

### Audit log not created

Check Vault has write permissions:
```bash
docker exec shared_vault_server ls -la /vault/logs/
```

## Enabled

- TLS encryption for all communications
- Audit logging for compliance and forensics
