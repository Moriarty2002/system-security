# HashiCorp Vault Integration

This project uses HashiCorp Vault for secure secrets management following security best practices.

## Architecture Overview

The project is split into two separate Docker Compose environments:

1. **Vault Infrastructure** (`docker-compose.vault.yaml`)
   - Runs independently from the application
   - Manages all secrets (database credentials, JWT keys, user passwords)
   - Uses file-based storage with persistent volume
   - Accessible on port 8200

2. **Application Stack** (`docker-compose.yaml`)
   - Apache frontend (ports 80, 443)
   - Flask backend
   - PostgreSQL database
   - Connects to Vault via external network

This separation provides:
- **Security**: Vault can be deployed on a separate host/network in production
- **Flexibility**: Vault lifecycle is independent of application
- **Scalability**: Multiple applications can share the same Vault instance
- **Best Practice**: Follows the principle of separation of concerns

## Security Features

### Secrets Management
- ✅ **No hardcoded credentials**: All secrets stored in Vault
- ✅ **JWT signing keys**: Generated and managed by Vault
- ✅ **Database passwords**: Dynamic, rotatable credentials
- ✅ **User passwords**: Default passwords managed securely
- ✅ **AppRole authentication**: Secure machine-to-machine auth
- ✅ **Token renewal**: Automatic token lifecycle management

### Access Control
- ✅ **Policy-based access**: Fine-grained permissions via Vault policies
- ✅ **Least privilege**: Application only reads required secrets
- ✅ **Audit logging**: All Vault access is logged
- ✅ **Secret versioning**: KV v2 engine tracks secret changes

### Infrastructure Security
- ✅ **Network isolation**: Separate Docker networks
- ✅ **Docker secrets**: Database password via Docker secrets
- ✅ **Capability dropping**: Minimal container permissions
- ✅ **Read-only mounts**: Config files mounted read-only

## Quick Start

### 1. Start Vault Infrastructure

```bash
# Start Vault server
docker compose -f docker-compose.vault.yaml up -d

# Wait for Vault to be ready (5-10 seconds)
sleep 10

# Initialize and configure Vault
cd vault/scripts
./init-vault.sh
```

This script will:
- Initialize Vault with 5 key shares (3 required to unseal)
- Unseal Vault automatically
- Enable KV v2 secrets engine
- Create application and admin policies
- Configure AppRole authentication
- Generate secure secrets (JWT key, database password)
- Create `.env` file with Vault credentials

**Important Files Created:**
- `vault/scripts/vault-keys.json` - Unseal keys and root token (⚠️ KEEP SECURE)
- `vault/scripts/approle-credentials.txt` - AppRole credentials
- `.env` - Application environment variables

### 2. Prepare Application Secrets

The init script creates a `.env` file with Vault credentials. It should look like:

```bash
# Vault Configuration
VAULT_ADDR=http://vault_server:8200
VAULT_ROLE_ID=<generated-role-id>
VAULT_SECRET_ID=<generated-secret-id>

# Application Configuration
FLASK_ENV=production
PYTHONUNBUFFERED=1
```

The script also creates a database password file:

```bash
# Create secrets directory
mkdir -p secrets

# Extract database password from Vault
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=$(jq -r '.root_token' vault/scripts/vault-keys.json)
vault kv get -field=password secret/database/postgres > secrets/db_password.txt
```

Or the init script can be updated to do this automatically.

### 3. Start Application Stack

```bash
# Ensure .env and secrets/db_password.txt exist
ls -la .env secrets/db_password.txt

# Start application
docker compose up -d

# Check logs
docker compose logs -f backend
```

### 4. Verify Integration

```bash
# Check backend logs for Vault integration
docker compose logs backend | grep Vault

# Expected output:
# ✅ Vault integration enabled - secrets managed by Vault
# Successfully authenticated with Vault using AppRole
# Using database configuration from Vault
```

## Vault Management

### Unseal Vault After Restart

Vault is sealed after every restart for security. Unseal it with:

```bash
cd vault/scripts
./unseal-vault.sh
```

### Rotate AppRole Secret ID

Regularly rotate the Secret ID for enhanced security:

```bash
cd vault/scripts
./rotate-secret-id.sh

# Update .env with new VAULT_SECRET_ID
# Restart application
docker compose restart backend
```

### Access Vault UI

1. Get root token: `cat vault/scripts/vault-keys.json | jq -r '.root_token'`
2. Open browser: http://localhost:8200
3. Login with root token
4. Navigate to secrets at: secret/

### View Secrets

```bash
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=$(jq -r '.root_token' vault/scripts/vault-keys.json)

# View application secrets
vault kv get secret/app/flask

# View database credentials
vault kv get secret/database/postgres
```

### Update Secrets

```bash
# Update JWT secret
vault kv patch secret/app/flask jwt_secret="new-secret-key"

# Update database password (requires coordinated DB update)
vault kv patch secret/database/postgres password="new-db-password"

# Invalidate application cache
docker compose restart backend
```

## Architecture Details

### Vault Policies

**app-policy.hcl** - Flask application permissions:
- Read secrets from `secret/data/app/*`
- Read database credentials from `secret/data/database/*`
- Renew and lookup own tokens
- Access AppRole authentication

**admin-policy.hcl** - Administrative permissions:
- Full access to all secrets
- Manage authentication methods
- Manage policies
- System administration

### AppRole Authentication Flow

1. Application starts with `VAULT_ROLE_ID` and `VAULT_SECRET_ID`
2. App authenticates to Vault using AppRole
3. Vault returns a time-limited token (1 hour)
4. App uses token to read secrets
5. Token is automatically renewed before expiry
6. Secrets are cached (5 minutes) to reduce Vault load

### Secret Hierarchy

```
secret/
├── app/
│   └── flask/
│       ├── jwt_secret          (JWT signing key)
│       ├── admin_password      (Default admin password)
│       ├── alice_password      (Default alice password)
│       └── moderator_password  (Default moderator password)
└── database/
    └── postgres/
        ├── username            (Database username)
        ├── password            (Database password)
        ├── database            (Database name)
        ├── host                (Database hostname)
        └── port                (Database port)
```

### Fallback Behavior

The application gracefully degrades if Vault is unavailable:

1. **Vault available**: Uses secrets from Vault (✅ recommended)
2. **Vault unavailable**: Falls back to environment variables (⚠️ less secure)
3. **Neither available**: Uses hardcoded defaults (❌ development only)

Check logs to verify which mode is active.

## Production Considerations

### High Availability

For production, consider:
- Multiple Vault instances with Consul backend
- Load balancing across Vault servers
- Geographic distribution for disaster recovery
- Automated unsealing with cloud KMS

### Secret Rotation

Implement regular secret rotation:
- AppRole Secret ID: Every 30-90 days
- JWT signing keys: Every 90-180 days (requires coordinated rollover)
- Database passwords: Every 90 days (use Vault's database engine)
- Application secrets: As needed

### TLS Configuration

Enable TLS for Vault in production:

```hcl
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 0
  tls_cert_file = "/vault/certs/vault.crt"
  tls_key_file = "/vault/certs/vault.key"
}
```

Update `VAULT_ADDR` to use `https://`.

### Monitoring

Monitor Vault health:
- `/v1/sys/health` endpoint
- Audit logs in `/vault/logs`
- Token expiration metrics
- Secret access patterns

### Backup and Recovery

**Critical backups:**
1. `vault-keys.json` - Store in secure location (encrypted, offline)
2. Vault data volume - Regular snapshots
3. Database volume - Regular backups
4. SSL certificates - Secure backup

**Recovery process:**
1. Restore Vault data volume
2. Start Vault server
3. Unseal with keys from `vault-keys.json`
4. Verify secret access
5. Restore application

## Troubleshooting

### Vault is sealed

```bash
cd vault/scripts
./unseal-vault.sh
```

### Application can't connect to Vault

```bash
# Check Vault is running
docker compose -f docker-compose.vault.yaml ps

# Check network connectivity
docker compose exec backend ping vault_server

# Check Vault credentials
docker compose exec backend env | grep VAULT

# Check Vault logs
docker compose -f docker-compose.vault.yaml logs vault
```

### Token expired

```bash
# Rotate Secret ID
cd vault/scripts
./rotate-secret-id.sh

# Update .env and restart
docker compose restart backend
```

### Lost unseal keys

**⚠️ WARNING**: Without unseal keys, Vault data is **permanently inaccessible**.
Always keep secure backups of `vault-keys.json`.

## References

- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [AppRole Auth Method](https://www.vaultproject.io/docs/auth/approle)
- [KV Secrets Engine v2](https://www.vaultproject.io/docs/secrets/kv/kv-v2)
- [Vault Best Practices](https://www.vaultproject.io/docs/internals/security)
