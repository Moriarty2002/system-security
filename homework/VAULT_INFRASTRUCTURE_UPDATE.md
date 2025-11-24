# System Security Homework - Vault Infrastructure

## 🚀 Getting Started

### For First-Time Setup

1. **Start Shared Vault Infrastructure**
   ```bash
   cd homework/vault-infrastructure
   docker compose up -d
   ```

2. **Initialize Vault (once)**
   ```bash
   cd scripts
   ./init-vault.sh
   ```
   This creates `vault-keys.json` - **keep it secure!**

3. **Configure Your Application**
   ```bash
   cd ../../4_LDAP_XACML/vault/scripts
   ./setup-vault-app.sh
   ```

4. **Start Your Application**
   ```bash
   cd ../..
   docker compose up -d
   ```

### For Subsequent Use

If Vault is already running and initialized:

```bash
# 1. Unseal Vault (after system restart)
cd homework/vault-infrastructure/scripts
./unseal-vault.sh

# 2. Start your application
cd ../../4_LDAP_XACML
docker compose up -d
```

## 🔐 Security Improvements

### Namespace Isolation
Each application has its own namespace in Vault:
- `4_LDAP_XACML` → `secret/4_ldap_xacml/`
- Future apps → `secret/[app-name]/`

### Policy Scoping
Application policies are now scoped to only their namespace:
```hcl
# 4_LDAP_XACML can only access its own secrets
path "secret/data/4_ldap_xacml/*" {
  capabilities = ["read"]
}
```

### AppRole Naming
AppRoles are prefixed with application name:
- `4_ldap_xacml-flask-app` (not just `flask-app`)
- Prevents collisions when multiple apps use Vault

## 📊 Benefits

### 1. Production-Like Architecture
Real production environments typically have:
- Centralized secrets management (like this)
- Multiple applications using the same Vault cluster
- Network isolation between Vault and applications

### 2. Resource Efficiency
- **Before**: N applications = N Vault containers
- **After**: N applications = 1 Vault container

### 3. Easier Management
- One Vault to initialize, unseal, and maintain
- Centralized secret rotation and auditing
- Single point for backup and disaster recovery

### 4. Scalability
Adding a new application that needs secrets:
1. Create application-specific policies
2. Create AppRole for the application
3. Store secrets in namespaced path
4. Connect application to `shared_vault_net`

## 🔧 Management

### Check Vault Status
```bash
docker exec shared_vault_server vault status
```

### Unseal Vault
```bash
cd homework/vault-infrastructure/scripts
./unseal-vault.sh
```

### Access Vault UI
- URL: http://localhost:8200
- Token: Found in `vault-infrastructure/scripts/vault-keys.json`

### View Logs
```bash
cd homework/vault-infrastructure
docker compose logs -f vault
```

### Stop Vault
⚠️ **Warning**: This affects all applications using Vault!
```bash
cd homework/vault-infrastructure
docker compose down
```

## 📁 Important Files

### Shared Infrastructure
- `vault-infrastructure/scripts/vault-keys.json` - **Critical**: Unseal keys and root token
- `vault-infrastructure/docker-compose.yaml` - Vault service definition

### Application-Specific
- `4_LDAP_XACML/.env` - Application environment variables with AppRole credentials
- `4_LDAP_XACML/vault/scripts/approle-credentials.txt` - AppRole credentials for the app
- `4_LDAP_XACML/secrets/db_password.txt` - Database password from Vault

**Security Note**: All these files are in `.gitignore` and should NEVER be committed!

## 🔄 Migration Notes

### Changes to Existing Application

1. **Docker Network**: Changed from `4_ldap_xacml_vault_net` to `shared_vault_net`
2. **Container Name**: `vault_server` → `shared_vault_server`
3. **Vault Address**: Now points to shared Vault
4. **Secret Paths**: `secret/app/` → `secret/4_ldap_xacml/app/`
5. **AppRole Name**: `flask-app` → `4_ldap_xacml-flask-app`

### Backward Compatibility

The old `docker-compose.vault.yaml` has been renamed to `docker-compose.vault.yaml.old` as a backup. To use the new setup:
- Delete or ignore the old file
- Use the shared infrastructure instead

## 🎓 Learning Objectives

This change demonstrates:
- **Microservices Architecture**: Services communicate over networks
- **Secrets Management**: Centralized, not embedded in applications
- **Infrastructure as Code**: Reproducible, documented setup
- **Security Best Practices**: Least privilege, network isolation, secret rotation
- **Production Patterns**: Real-world deployment scenarios

## 🆘 Troubleshooting

### Application can't connect to Vault
- Check if Vault is running: `docker ps | grep shared_vault_server`
- Check if Vault is unsealed: `docker exec shared_vault_server vault status`
- Verify network connection: Application must be on `shared_vault_net`

### "permission denied" errors in application logs
- Check AppRole credentials in `.env`
- Verify policies are correctly configured for the app
- Ensure secrets exist at the namespaced path

### Lost vault-keys.json
⚠️ **Critical**: If Vault is sealed and you lose this file, data is unrecoverable!
- Always keep backups in secure locations
- Consider using a password manager or encrypted storage

## 📚 Additional Resources

- [vault-infrastructure/README.md](vault-infrastructure/README.md) - Detailed Vault documentation
- [4_LDAP_XACML/README.md](4_LDAP_XACML/README.md) - Application-specific documentation
- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)

## 🔮 Future Enhancements

Potential additions:
1. Add more applications that use the shared Vault
2. Implement Vault audit logging
3. Add TLS encryption for Vault communication
4. Configure automatic secret rotation
5. Implement Vault HA with Raft storage
