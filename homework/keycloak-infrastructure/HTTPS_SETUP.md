# Keycloak HTTPS Configuration - Summary

## ✅ Implementation Complete

Keycloak now uses **HTTPS with certificates managed by Vault's PKI**, sharing the same CA as the Apache server.

## Key Features

### 1. Shared PKI Infrastructure
- **PKI Engine**: `pki_localhost` (same as Apache)
- **PKI Role**: `keycloak-server-localhost`
- **Same CA**: Both Apache and Keycloak use the same Certificate Authority
- **Benefit**: Clients only need to trust one CA certificate

### 2. Automatic Certificate Management
- Certificates automatically generated at startup from Vault
- Auto-renewal when certificate expires in < 7 days
- No manual certificate management required
- 90-day default validity (configurable up to 1 year)

### 3. Security Features
- TLS 1.2+ with RSA 2048-bit keys
- Subject Alternative Names (SANs): localhost, shared-keycloak-server, keycloak
- IP SAN: 127.0.0.1
- Certificate stored securely inside container
- Private key permissions: 600 (readable only by keycloak user)

## Access Points

- **HTTPS**: https://localhost:8443 (recommended)
- **HTTP**: http://localhost:8080 (fallback for development)

## Certificate Details

```
Common Name: localhost
Subject Alternative Names:
  - DNS: localhost
  - DNS: shared-keycloak-server
  - DNS: keycloak
  - IP: 127.0.0.1
Issuer: pki_localhost CA (shared with Apache)
Validity: 90 days (auto-renewed)
Key Type: RSA 2048
```

## Trust the CA Certificate

To trust Keycloak's certificate in your browser:

1. **Export CA Certificate**:
   ```bash
   docker exec shared_vault_server vault read -field=certificate pki_localhost/cert/ca > ca.crt
   ```

2. **Import to Browser**:
   - **Firefox**: Settings → Privacy & Security → Certificates → View Certificates → Import
   - **Chrome**: Settings → Security → Manage Certificates → Authorities → Import
   - **Safari**: Keychain Access → File → Import Items

3. **Verify**: Visit https://localhost:8443 - no certificate warning!

## Configuration Files

### Modified Files
1. `docker-compose.yaml` - Added HTTPS port 8443 and certificate configuration
2. `scripts/keycloak-entrypoint.sh` - Added automatic certificate fetching from Vault PKI
3. `policies/keycloak-policy.hcl` - Added PKI permissions for certificate generation
4. `.env` - Contains only AppRole credentials (no certificate paths)

### New Scripts
1. `scripts/setup-shared-pki-role.sh` - Creates Keycloak role in pki_localhost
2. `scripts/setup-vault-pki.sh` - (deprecated - was for separate PKI)
3. `scripts/fetch-keycloak-certificates.sh` - Manual certificate generation utility

## Setup Commands

```bash
# 1. Setup Keycloak role in shared PKI
cd keycloak-infrastructure
./scripts/setup-shared-pki-role.sh

# 2. Restart Keycloak to generate certificate
docker compose restart keycloak

# 3. Verify HTTPS is working
docker compose ps
docker compose logs keycloak | grep "certificate generated"

# 4. Access via HTTPS
curl -k https://localhost:8443  # -k to skip verification without CA trust
```

## Logs Verification

Successful startup shows:
```
🔐 Fetching TLS certificates from Vault PKI...
  ✅ New certificate generated (expires: 2026-02-26)
=========================================
Starting Keycloak...
=========================================
Listening on: http://0.0.0.0:8080 and https://0.0.0.0:8443
```

## Integration with Application

Update `4_three_tier_app/.env`:
```bash
# Use HTTPS for Keycloak
KEYCLOAK_SERVER_URL=https://shared-keycloak-server:8443
```

The Flask backend will now connect to Keycloak via HTTPS using the shared CA.

## Maintenance

### Certificate Rotation
- **Automatic**: Certificates auto-renew when < 7 days to expiration
- **Manual**: Restart Keycloak to force renewal: `docker compose restart keycloak`
- **Check Expiration**: `docker exec shared-keycloak-server ls -l /opt/keycloak/certs/`

### Update Certificate TTL
Edit `scripts/keycloak-entrypoint.sh` and change `ttl="2160h"` (default: 90 days)

### Troubleshooting

**Certificate not generated**:
```bash
# Check Vault connection
docker exec shared-keycloak-server vault status

# Check PKI role exists
docker exec shared_vault_server vault list pki_localhost/roles

# Check logs
docker compose logs keycloak
```

**HTTPS not working**:
```bash
# Verify certificate files exist
docker exec shared-keycloak-server ls -lh /opt/keycloak/certs/

# Check Keycloak is listening on 8443
docker exec shared-keycloak-server ss -tlnp | grep 8443

# Verify environment variables
docker exec shared-keycloak-server env | grep KC_HTTPS
```

## Security Considerations

✅ **Implemented**:
- TLS certificates from Vault PKI (not self-signed)
- Automatic certificate renewal
- Secure private key storage (600 permissions)
- Same CA as Apache (unified trust)
- Certificate validation with SANs

⚠️ **Development Mode**:
- HTTP still enabled (port 8080) - disable in production
- Development mode warnings in logs - use production mode for deployment

🔒 **Production Recommendations**:
1. Disable HTTP: Remove `KC_HTTP_ENABLED: true`
2. Use production mode: Change `start-dev` to `start`
3. Enable strict hostname: `KC_HOSTNAME_STRICT: true`
4. Configure load balancer for external HTTPS
5. Use shorter certificate TTL (30 days) for better security

## Related Documentation

- [VAULT_INTEGRATION.md](VAULT_INTEGRATION.md) - Complete Vault integration guide
- [README.md](README.md) - General infrastructure documentation
- [QUICK_START.md](QUICK_START.md) - Quick setup guide
