# System and Communications Protection Procedures

## Document Control
- **Version**: 1.0
- **Effective Date**: 12 December 2025
- **Review Date**: December 2026
- **Owner**: Marcello Esposito

## 1. Purpose
These procedures implement the System and Communications Protection Policy and provide step-by-step guidance for security operations.

## 2. TLS Certificate Management

### 2.1 Certificate Generation (Vault PKI)
1. Ensure Vault is running and unsealed
2. Verify PKI engine is enabled: `vault secrets list`
3. Generate certificate via Vault API:
   ```bash
   vault write pki_localhost/issue/<role-name> \
     common_name="localhost" \
     ttl="720h"
   ```
4. Extract certificate and private key from response
5. Deploy to application (Apache, Keycloak)
6. Verify TLS configuration: `openssl s_client -connect localhost:443`

**Implementation:** See `apache/scripts/entrypoint.sh` for automated certificate retrieval

### 2.2 Certificate Renewal
1. Certificates expire after 30 days (default TTL)
2. Application startup scripts fetch new certificates from Vault PKI
3. For manual renewal:
   - Stop the service
   - Delete old certificate files
   - Restart service (entrypoint fetches new certificate)
4. Monitor certificate expiration via logs

## 3. Vault Secret Management

### 3.1 Secret Rotation
1. Access Vault UI at https://localhost:8200 or use CLI
2. Update secret value:
   ```bash
   vault kv put secret/mes_local_cloud/app/example_secret value="new_value"
   ```
3. Restart affected services to load new secret
4. Verify application functionality after rotation

### 3.2 AppRole Management
1. Create AppRole for new service:
   ```bash
   vault write auth/approle/role/<role-name> \
     token_ttl=1h \
     token_max_ttl=4h \
     policies="app-policy"
   ```
2. Fetch Role ID and Secret ID
3. Store credentials securely in service environment
4. Service authenticates at startup using AppRole

**Implementation:** See `vault/scripts/setup-vault-approle.sh`

## 4. Network Security Configuration

### 4.1 Network Segmentation
Docker networks are defined in `docker-compose.yaml`:
- **shared_vault_net**: Isolated Vault communication
- **shared_keycloak_network**: Keycloak and authentication services
- **app_net**: Internal application components

**Procedure:**
1. Services connect to required networks only (least privilege)
2. Database accessible only via `app_net` (no external ports)
3. Backend accessible only via Apache reverse proxy
4. Verify isolation: `docker network inspect <network-name>`

### 4.2 Port Exposure Management
1. External ports limited to 80, 443 (Apache), 8443 (Keycloak)
2. Bind to localhost only: `127.0.0.1:8200:8200` (Vault)
3. Internal services use Docker network DNS
4. Review port exposure: `docker compose ps`

## 5. Security Monitoring

### 5.1 Vault Audit Log Review
1. Enable audit logging:
   ```bash
   cd ../vault-infrastructure/scripts
   ./enable-audit-logging.sh
   ```
2. Review audit logs:
   ```bash
   docker exec shared_vault_server cat /vault/logs/audit.log | jq
   ```
3. Monitor for:
   - Failed authentication attempts
   - Unauthorized secret access attempts
   - Policy violations
   - Unusual access patterns

### 5.2 Application Log Review
1. View application logs:
   ```bash
   docker compose logs -f backend
   docker compose logs -f apache-fe
   ```
2. Check Keycloak authentication events via Admin Console
3. Review weekly for security incidents
4. Investigate anomalies immediately

## 6. Incident Response

### 6.1 Suspected Credential Compromise
1. Immediately rotate compromised secret in Vault
2. Review audit logs for unauthorized access
3. Identify affected systems
4. Restart services to load new credentials
5. Document incident and remediation actions

### 6.2 TLS Certificate Issues
1. Check certificate expiration: `openssl x509 -in cert.pem -noout -dates`
2. Verify Vault PKI is accessible
3. Regenerate certificate from Vault
4. Restart affected service
5. Test connectivity with `curl -v https://localhost`

### 6.3 Network Security Incident
1. Review Docker network configuration
2. Check for unexpected port exposure: `netstat -tulpn`
3. Verify firewall rules if applicable
4. Isolate compromised containers
5. Restore from known-good configuration

## 7. Configuration Backup and Recovery

### 7.1 Vault Backup
1. Vault data stored in volume: `vault_data`
2. Backup unseal keys: `vault-infrastructure/scripts/vault-keys.json`
3. Export secrets before major changes:
   ```bash
   vault kv get -format=json secret/mes_local_cloud/app/ > backup.json
   ```
4. Store backups securely (encrypted, off-system)

### 7.2 Configuration Backup
1. All configuration in version control (Git)
2. Docker volumes contain runtime data
3. Before changes: `docker compose down` and backup volumes
4. Recovery: restore configuration files and `docker compose up`

## 8. Compliance Activities

### 8.1 Security Reviews
- **Monthly**: Review authentication logs for anomalies
- **Quarterly**: Verify TLS configuration meets policy
- **Annual**: Complete SC-1 policy and procedures review

### 8.2 Testing
- **After configuration changes**: Test TLS connectivity
- **After secret rotation**: Verify application functionality
- **Quarterly**: Conduct security configuration audit

### 8.3 Training
- New administrators review SC-1 policy and procedures
- Annual refresher on cryptographic best practices
- Training on Vault and certificate management tools

## 9. Procedure Review
- Procedures reviewed annually (December each year)
- Updated after significant technical changes
- Updates coordinated with policy reviews
- Version history maintained in document control

## 10. Related Documents
- SC-1 Policy Document
- Vault Infrastructure README
- Keycloak Infrastructure README
- Application Architecture Documentation
