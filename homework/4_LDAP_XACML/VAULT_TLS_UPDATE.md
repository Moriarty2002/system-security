# Quick Fix Guide: Reconnecting 4_LDAP_XACML to TLS-Enabled Vault

## What Changed

The Vault server now uses HTTPS instead of HTTP. All application configurations have been updated to:
- Use `https://shared_vault_server:8200` instead of `http://`
- Skip TLS verification for self-signed certificates (VAULT_SKIP_VERIFY=1)

## Quick Restart Steps

```bash
# 1. Restart the 4_LDAP_XACML application
cd /shared/University/system_security/system-security/homework/4_LDAP_XACML
docker compose down
docker compose up -d

# 2. Verify connections
docker compose logs backend | grep -i vault
docker compose logs apache-fe | grep -i vault
```

## Files Updated

1. **`.env`** - Changed VAULT_ADDR to use HTTPS
2. **`docker-compose.yaml`** - Added VAULT_SKIP_VERIFY=1 environment variable
3. **`be_flask/src/vault_client.py`** - Added TLS verification skip support
4. **`apache/scripts/entrypoint.sh`** - Added --no-check-certificate to wget calls
5. **`vault/scripts/setup-vault-app.sh`** - Updated for HTTPS

## Verification

Check that containers can connect to Vault:

```bash
# Test backend connection
docker exec flask_be python3 -c "
import os
os.environ['VAULT_SKIP_VERIFY'] = '1'
import hvac
client = hvac.Client(url='https://shared_vault_server:8200', verify=False)
print('✅ Backend can connect to Vault:', client.sys.read_health_status())
"

# Test Apache connection
docker exec apache_fe wget --no-check-certificate -qO- https://shared_vault_server:8200/v1/sys/health
```

## Troubleshooting

### "SSL certificate problem" errors
- Make sure `VAULT_SKIP_VERIFY=1` is set in docker-compose.yaml
- Restart containers after updating configuration

### "Connection refused" errors
- Ensure Vault is running: `docker ps | grep vault`
- Check Vault is unsealed: `cd vault-infrastructure/scripts && ./unseal-vault.sh`
- Verify network connectivity: `docker exec flask_be ping -c 2 shared_vault_server`

### Still seeing HTTP URLs
- Check `.env` file has `VAULT_ADDR=https://...`
- Rebuild containers: `docker compose build --no-cache`
- Restart: `docker compose up -d`
