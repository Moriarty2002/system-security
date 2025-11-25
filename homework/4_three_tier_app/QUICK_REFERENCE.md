# Quick Reference - Vault-Integrated Application

## One-Command Setup

```bash
./setup.sh
```

This handles everything: Vault initialization, secret generation, and application startup.

## Manual Setup (Step by Step)

```bash
# 1. Start Vault
docker compose -f docker-compose.vault.yaml up -d
sleep 10

# 2. Initialize Vault
cd vault/scripts && ./init-vault.sh && cd ../..

# 3. Start Application
docker compose up -d
```

## Common Commands

### Vault Management

```bash
# Unseal Vault (after restart)
cd vault/scripts && ./unseal-vault.sh

# View secrets
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=$(jq -r '.root_token' vault/scripts/vault-keys.json)
vault kv get secret/app/flask
vault kv get secret/database/postgres

# Update a secret
vault kv patch secret/app/flask jwt_secret="new-key"

# Rotate AppRole credentials
cd vault/scripts && ./rotate-secret-id.sh
```

### Application Management

```bash
# View logs
docker compose logs -f backend
docker compose logs -f db

# Restart backend
docker compose restart backend

# Stop all
docker compose down

# Complete reset
./setup.sh --reset
```

### Troubleshooting

```bash
# Check Vault connection
docker compose exec backend python3 -c "
from src.vault_client import get_vault_client
print('Vault available:', get_vault_client().is_available())
"

# Check service status
docker compose ps
docker compose -f docker-compose.vault.yaml ps

# View Vault status
export VAULT_ADDR=http://localhost:8200
vault status

# Check networks
docker network ls | grep -E "vault|app"
```

## Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Application | http://localhost | admin/admin123, alice/alice123 |
| Vault UI | http://localhost:8200 | Token from vault-keys.json |
| MinIO Console | http://localhost:9001 | minioadmin/minioadmin |
| Backend API | http://localhost:5000 | JWT from /auth/login |
| Database | localhost:5432 | From Vault secrets |

## Important Files

| File | Purpose | Security |
|------|---------|----------|
| `.env` | Vault credentials | ⚠️ Never commit |
| `vault/scripts/vault-keys.json` | Unseal keys | 🔒 Backup securely |
| `secrets/db_password.txt` | DB password | 🔒 Auto-generated |
| `.gitignore` | Protects secrets | ✅ Already configured |

## Vault Secret Paths

```
secret/
├── app/flask/
│   ├── jwt_secret              # JWT signing key
│   ├── admin_password          # Default password
│   ├── alice_password          # Default password
│   └── moderator_password      # Default password
└── database/postgres/
    ├── username                # DB username
    ├── password                # DB password (also in secrets/db_password.txt)
    ├── database                # DB name
    ├── host                    # DB host
    └── port                    # DB port
```

## Security Checklist

- [ ] Vault initialized and unsealed
- [ ] vault-keys.json backed up securely
- [ ] .env file has correct AppRole credentials
- [ ] secrets/db_password.txt exists
- [ ] Backend logs show "Vault integration enabled"
- [ ] Database connection successful
- [ ] Can login with test users
- [ ] .gitignore protects sensitive files

## Emergency Procedures

### Lost Vault Access

If you lose vault-keys.json:
- ❌ Vault data is **permanently inaccessible**
- 🔄 Must reset and reinitialize: `./setup.sh --reset`
- ⚠️ **Always backup vault-keys.json!**

### Vault Sealed After Restart

```bash
cd vault/scripts && ./unseal-vault.sh
```

### Backend Can't Connect to Vault

```bash
# 1. Check Vault is running
docker compose -f docker-compose.vault.yaml ps

# 2. Unseal if needed
cd vault/scripts && ./unseal-vault.sh

# 3. Verify credentials
cat .env | grep VAULT

# 4. Restart backend
docker compose restart backend
```

### Token Expired

```bash
# Rotate Secret ID
cd vault/scripts && ./rotate-secret-id.sh

# Update .env with new VAULT_SECRET_ID
# Then restart
docker compose restart backend
```

## Production Recommendations

1. **Separate Infrastructure**: Deploy Vault on dedicated hosts
2. **Enable TLS**: Configure HTTPS for Vault
3. **High Availability**: Use Consul backend and multiple Vault instances
4. **Auto-Unseal**: Integrate with cloud KMS (AWS, Azure, GCP)
5. **Monitoring**: Set up Vault metrics and alerting
6. **Backup Strategy**: Automated backups of Vault data
7. **Secret Rotation**: Regular rotation of AppRole Secret ID
8. **Audit Review**: Regular review of Vault audit logs

## Documentation

- **README.md**: Quick start and overview
- **VAULT_INTEGRATION.md**: Detailed Vault documentation
- **IMPLEMENTATION_SUMMARY.md**: Technical implementation details
- **.env.example**: Configuration template

## Support

For issues or questions:
1. Check logs: `docker compose logs backend`
2. Review VAULT_INTEGRATION.md troubleshooting section
3. Verify all services running: `docker compose ps`
4. Check Vault seal status: `vault status`

---

**Remember**: 
- Keep vault-keys.json secure and backed up
- Never commit secrets to version control
- Rotate credentials regularly
- Monitor Vault audit logs
