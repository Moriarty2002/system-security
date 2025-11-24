# Vault Infrastructure Quick Reference

## 🚀 Common Commands

### Start Vault
```bash
cd homework/vault-infrastructure
docker compose up -d
```

### Stop Vault
```bash
cd homework/vault-infrastructure
docker compose down
```

### Initialize Vault (First Time Only)
```bash
cd homework/vault-infrastructure/scripts
./init-vault.sh
```

### Unseal Vault (After Each Restart)
```bash
cd homework/vault-infrastructure/scripts
./unseal-vault.sh
```

### Check Vault Status
```bash
docker exec shared_vault_server vault status
```

### Access Vault UI
- URL: http://localhost:8200
- Token: In `vault-infrastructure/scripts/vault-keys.json`

## 🔧 Application Integration

### Configure New Application
1. Create application-specific policies in app's `vault/policies/`
2. Run setup script to create AppRole and store secrets
3. Update app's `docker-compose.yaml` to connect to `shared_vault_net`
4. Use namespaced secret paths: `secret/[app-name]/`

### Application-Specific Setup (Example: 4_LDAP_XACML)
```bash
cd homework/4_LDAP_XACML/vault/scripts
./setup-vault-app.sh
```

### Rotate Application Credentials
```bash
cd homework/4_LDAP_XACML/vault/scripts
./rotate-secret-id.sh
# Update app's .env and restart
```

## 📊 Vault Operations

### List All Secrets
```bash
docker exec -e VAULT_TOKEN="<token>" shared_vault_server vault kv list secret/
```

### Read Secret
```bash
docker exec -e VAULT_TOKEN="<token>" shared_vault_server vault kv get secret/4_ldap_xacml/app/flask
```

### Write Secret
```bash
docker exec -e VAULT_TOKEN="<token>" shared_vault_server vault kv put secret/4_ldap_xacml/app/new key=value
```

### List Policies
```bash
docker exec -e VAULT_TOKEN="<token>" shared_vault_server vault policy list
```

### Read Policy
```bash
docker exec -e VAULT_TOKEN="<token>" shared_vault_server vault policy read 4_ldap_xacml-app
```

## 🔐 Security

### Important Files to Protect
- `vault-infrastructure/scripts/vault-keys.json` - Unseal keys and root token
- `*/vault/scripts/approle-credentials.txt` - AppRole credentials
- `*/.env` - Application environment variables
- `*/secrets/` - Docker secrets

### Security Checklist
- [ ] vault-keys.json backed up securely
- [ ] File permissions set: `chmod 600` on sensitive files
- [ ] Sensitive files in .gitignore
- [ ] Root token not used in applications (use AppRole)
- [ ] Secrets namespaced per application
- [ ] Policies follow least privilege

## 🐛 Troubleshooting

### Vault is Sealed
```bash
cd homework/vault-infrastructure/scripts
./unseal-vault.sh
```

### Application Can't Connect
1. Check Vault is running: `docker ps | grep shared_vault_server`
2. Check Vault is unsealed: `docker exec shared_vault_server vault status`
3. Verify app is on `shared_vault_net` network
4. Check VAULT_ADDR in app's .env

### Permission Denied
1. Verify AppRole credentials in .env
2. Check policy has correct paths and capabilities
3. Ensure secrets exist at expected path

### Lost vault-keys.json
⚠️ Data is unrecoverable if Vault is sealed. Always keep backups!

## 📁 Directory Structure

```
homework/
├── vault-infrastructure/        # Shared Vault server
│   ├── docker-compose.yaml
│   ├── config/vault-config.hcl
│   ├── scripts/
│   │   ├── init-vault.sh
│   │   ├── unseal-vault.sh
│   │   └── vault-keys.json      # 🔐 SECURE THIS
│   └── README.md
│
└── 4_LDAP_XACML/               # Application
    ├── docker-compose.yaml      # Connects to shared_vault_net
    ├── .env                     # 🔐 SECURE THIS
    ├── vault/
    │   ├── policies/            # App-specific policies
    │   └── scripts/
    │       └── setup-vault-app.sh
    └── secrets/                 # 🔐 SECURE THIS
```

## 🔄 Workflow

### First Time Setup
1. Start Vault → Initialize → Configure App → Start App

### Daily Use
1. Unseal Vault (if sealed) → Start App

### After System Restart
1. Start Vault → Unseal → Start App

### Adding New Application
1. Create policies → Setup AppRole → Store secrets → Connect app

## 📚 Documentation

- [vault-infrastructure/README.md](vault-infrastructure/README.md) - Detailed Vault docs
- [VAULT_INFRASTRUCTURE_UPDATE.md](VAULT_INFRASTRUCTURE_UPDATE.md) - Migration guide
- [4_LDAP_XACML/README.md](4_LDAP_XACML/README.md) - Application docs
