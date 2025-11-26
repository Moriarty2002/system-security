# Shared Vault Infrastructure

This directory contains a centralized HashiCorp Vault server that can be used by multiple applications across different homework projects for secure secrets management.

## 🎯 Purpose

Instead of each application having its own Vault instance, this shared infrastructure provides:
- **Centralized secrets management** - One Vault instance for all applications
- **Production-like architecture** - Emulates real-world scenarios where Vault serves multiple apps
- **Resource efficiency** - Single Vault container instead of multiple instances
- **Easier management** - One place to manage all secrets and policies

## 🏗️ Architecture

```
homework/
├── vault-infrastructure/          # Shared Vault server
│   ├── docker-compose.yaml        # Vault service definition
│   ├── config/                    # Vault configuration
│   ├── policies/                  # Application-specific policies
│   ├── scripts/                   # Management scripts
│   └── logs/                      # Vault audit logs
│
├── 4_three_tier_app/                  # Application using Vault
│   ├── docker-compose.yaml        # Connects to shared vault
│   ├── vault/                     # App-specific Vault config
│   │   ├── policies/              # App policies
│   │   └── scripts/               # App setup scripts
│   └── ...
│
└── [other applications]/          # Can also use shared Vault
```

## 🚀 Quick Start

### 1. Start the Vault Server

```bash
cd homework/vault-infrastructure
docker compose up -d
```

### 2. Initialize Vault (First Time Only)

```bash
cd scripts
./init-vault.sh
```

This will:
- Initialize Vault with 5 unseal keys (requires 3 to unseal)
- Save keys to `vault-keys.json` ⚠️ **Keep this file secure!**
- Enable KV v2 secrets engine
- Enable AppRole authentication
- Unseal Vault

### 3. Unseal After Restart

Vault is sealed after each restart for security. Unseal it with:

```bash
cd scripts
./unseal-vault.sh
```

## 🔐 Security Notes

### Critical Files

- **vault-keys.json** - Contains unseal keys and root token
  - ⚠️ Never commit to git
  - ⚠️ Back up securely
  - ⚠️ Store in secure location (password manager, HSM, etc.)

### Network Isolation

- Vault runs on its own network: `shared_vault_net`
- Applications connect to this external network
- Network subnet: `172.30.0.0/16`

### Access Control

- Root token: For initial setup and admin tasks
- AppRole: For application authentication
- Policies: Define what each application can access

## 📋 Application Integration

### For Applications Using This Vault

Each application should:

1. **Connect to the Vault network** in `docker-compose.yaml`:
   ```yaml
   networks:
     vault_net:
       external: true
       name: shared_vault_net
   ```

2. **Configure Vault address**:
   ```
   VAULT_ADDR=http://shared_vault_server:8200
   ```

3. **Create application-specific policies** in `policies/`:
   ```hcl
   # Example: 4_three_tier_app/vault/policies/app-policy.hcl
   path "secret/data/4_ldap_xacml/*" {
     capabilities = ["read", "list"]
   }
   ```

4. **Set up AppRole** for authentication:
   ```bash
   # Create AppRole for your app
   vault write auth/approle/role/myapp-role \
     token_policies="myapp-policy" \
     token_ttl=1h \
     token_max_ttl=4h
   ```

5. **Store secrets** under application namespace:
   ```bash
   # Example: secrets for 4_three_tier_app
   vault kv put secret/4_ldap_xacml/database \
     username="admin" \
     password="secure_password"
   ```

## 🛠️ Management

### Check Vault Status

```bash
docker exec shared_vault_server vault status
```

### Access Vault UI

Open: http://localhost:8200

Login with root token from `vault-keys.json`

### View Logs

```bash
docker compose logs -f vault
```

### Stop Vault

```bash
docker compose down
# Note: Data persists in vault_data volume
```

### Complete Reset (⚠️ Destroys All Data)

```bash
docker compose down -v
rm -f scripts/vault-keys.json
# Then start fresh with init-vault.sh
```

## 📁 Directory Structure

```
vault-infrastructure/
├── docker-compose.yaml       # Vault service definition
├── README.md                 # This file
├── config/
│   └── vault-config.hcl      # Vault server configuration
├── policies/                 # Shared/common policies
├── scripts/
│   ├── init-vault.sh         # Initialize and configure Vault
│   └── unseal-vault.sh       # Unseal Vault after restart
└── logs/                     # Vault audit logs (if enabled)
```

## 🔄 Typical Workflow

### Initial Setup
```bash
# 1. Start Vault
cd homework/vault-infrastructure
docker compose up -d

# 2. Initialize (first time only)
cd scripts
./init-vault.sh

# 3. Backup vault-keys.json securely
cp vault-keys.json ~/secure-backup/
```

### Daily Use
```bash
# If Vault is sealed after restart
cd homework/vault-infrastructure/scripts
./unseal-vault.sh

# Then start your applications
cd ../../4_three_tier_app
./setup.sh
```

## 📖 Applications Using This Vault

- **4_three_tier_app**: File Storage Service with JWT authentication
  - Stores: DB credentials, JWT secrets, user passwords
  - Namespace: `secret/4_ldap_xacml/`

- *Add more applications here as they integrate*

## 🔧 Troubleshooting

### Vault is sealed
```bash
cd scripts
./unseal-vault.sh
```

### Connection refused
```bash
# Check if Vault is running
docker ps | grep shared_vault_server

# Check logs
docker compose logs vault
```

### Lost vault-keys.json
⚠️ If you lose this file and Vault is sealed, **data is unrecoverable**.
Always keep secure backups!

### Applications can't connect
- Ensure application is on `shared_vault_net` network
- Check `VAULT_ADDR=http://shared_vault_server:8200`
- Verify Vault is unsealed: `docker exec shared_vault_server vault status`

## 🎓 Best Practices

1. **Never commit secrets** - Use `.gitignore` for sensitive files
2. **Backup unseal keys** - Store in multiple secure locations
3. **Use AppRole** - Don't use root token in applications
4. **Namespace secrets** - Use `secret/app-name/` structure
5. **Rotate credentials** - Regularly rotate Secret IDs and passwords
6. **Monitor access** - Enable and review audit logs
7. **Production deployment** - Use TLS, separate host, proper auth

## 📚 Resources

- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [AppRole Authentication](https://www.vaultproject.io/docs/auth/approle)
- [KV Secrets Engine](https://www.vaultproject.io/docs/secrets/kv/kv-v2)
