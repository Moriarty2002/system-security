# Secure File Storage Service with Keycloak & HashiCorp Vault

A production-ready web application with enterprise-grade identity management (Keycloak) and secrets management (HashiCorp Vault).

## 🔐 Security Features

- **Keycloak Authentication**: Enterprise-grade identity and access management
  - OpenID Connect (OIDC) protocol
  - No passwords stored in application database
  - Single Sign-On (SSO) support
  - Centralized user management
- **HashiCorp Vault Integration**: All secrets managed by Vault
- **No Hardcoded Credentials**: Zero secrets in code or config files
- **AppRole Authentication**: Secure machine-to-machine authentication
- **Token Security**: RS256 signed tokens validated with Keycloak public keys
- **Database Security**: Credentials stored and rotated in Vault
- **MinIO Security**: Dedicated application user with bucket-only access
- **Docker Secrets**: Sensitive data passed via Docker secrets API
- **Network Isolation**: Separate networks for Vault and application
- **Least Privilege**: Minimal container capabilities and permissions

## 🏗️ Architecture

### Three-Tier Infrastructure

**1. Shared Vault Infrastructure** (Independent, at homework/vault-infrastructure/)
- HashiCorp Vault server
- Secrets storage and management
- Policy-based access control
- Audit logging
- **Shared by multiple applications**

**2. Identity Management** (Keycloak)
- User authentication and authorization
- OpenID Connect provider
- Role-based access control
- User federation support

**3. Application Stack** (This project: 4_three_tier_app)
- Apache HTTPS frontend
- Flask API backend with Keycloak integration
- PostgreSQL database (shared with Keycloak)
- MinIO object storage (S3-compatible)
- Connects to shared Vault for secrets

This separation enables:
- ✅ Independent Vault lifecycle
- ✅ Centralized identity management
- ✅ Multiple applications sharing infrastructure
- ✅ Production deployment on separate hosts
- ✅ Enhanced security through isolation
- ✅ Real-world architecture simulation

## 🚀 Quick Start

### Step 1: Initialize Shared Vault (First Time Only)

```bash
# Navigate to shared Vault infrastructure
cd ../vault-infrastructure

# Start Vault infrastructure
docker compose up -d

# Wait for Vault to be ready
sleep 10

# Initialize and configure Vault
cd scripts
./init-vault.sh
cd ../../4_three_tier_app
```

**⚠️ IMPORTANT**: The script creates `vault-keys.json` with unseal keys in `../vault-infrastructure/scripts/`. **Keep this file secure and backed up!**

### Step 2: Configure Application Secrets in Vault

```bash
# Configure application-specific secrets and policies
cd vault/scripts
./setup-vault-app.sh
cd ../..
```

This script:
- Creates namespaced policies for this application
- Generates AppRole credentials
- Stores secrets at `secret/mes_local_cloud/`
- Creates database initialization script with hashed passwords

### Step 3: Configure Keycloak in Vault

```bash
# Use the canonical Keycloak infrastructure script to configure Vault
# from the application directory:
../keycloak-infrastructure/scripts/store-secrets-in-vault.sh --generate
```

This command:
- Generates secure Keycloak admin credentials (with `--generate`)
- Stores configuration in Vault
- Updates or appends environment variables in `../keycloak-infrastructure/.env`
- Configures database access for Keycloak

**⚠️ SAVE THE KEYCLOAK ADMIN PASSWORD** displayed by the script!

### Step 4: Reset Database (First Time Setup)

Since the database init scripts were just generated, reset the database:

```bash
# Stop services and remove database volume
docker compose down -v
docker volume rm 4_three_tier_app_pg_data 2>/dev/null || true

# This ensures the init scripts run when database starts
```

### Step 5: Start Application

```bash
# Start the application stack (from 4_three_tier_app directory)
docker compose up -d

# Verify services are running
docker compose ps

# Check logs
docker compose logs -f keycloak
docker compose logs -f backend
```

### Step 6: Configure Keycloak

1. **Access Keycloak Admin Console**
   - URL: http://localhost:8080
   - Username: `admin`
   - Password: (from setup-keycloak-vault.sh output)

2. **Create Realm**
   - Click "Create Realm"
   - Name: `mes-local-cloud`
   - Save

3. **Create Client**
   - Go to Clients → Create client
   - Client ID: `mes-local-cloud-api`
   - Protocol: `openid-connect`
   - Client authentication: OFF (public client)
   - Standard flow: ON
   - Direct access grants: ON
   - Valid redirect URIs: `http://localhost/*`
   - Web origins: `http://localhost`
   - Save

4. **Create Roles**
   - Go to Realm roles → Create role
   - Create: `admin`, `moderator`, `user`

5. **Create Users**
   - Go to Users → Add user
   - Create users and assign roles
   - Set passwords (Credentials tab)
   - Example users: admin, moderator, alice

### Step 7: Access the Application

- **Application**: https://localhost (or http://localhost)
- **Keycloak Admin**: http://localhost:8080
- **MinIO Console**: http://localhost:9001

**Authentication**: Authentication is performed by Keycloak (OIDC). The application redirects users to Keycloak for login; no credentials are collected by the application itself.

## 📚 Documentation

- **[KEYCLOAK_MIGRATION.md](./KEYCLOAK_MIGRATION.md)** - Detailed Keycloak integration guide
- **[QUICK_SETUP_project+vault.md](./QUICK_SETUP_project+vault.md)** - Condensed setup instructions

## 🔑 Authentication Flow

1. User visits the application and is redirected to Keycloak for authentication (hosted login page)
2. User authenticates with Keycloak (supports username/password, social logins like Google, and 2FA configured in Keycloak)
3. Keycloak redirects back to the application with an authorization code; the frontend exchanges it (via the Keycloak adapter) and receives tokens
4. Frontend stores the access token in session storage and calls `GET /auth/whoami` to obtain user metadata
5. Backend validates tokens using Keycloak public keys (RS256) and creates/updates a local user profile on first login
6. Backend synchronizes roles from Keycloak to implement role-based access control

## 🗄️ Database Schema

### User Profiles (Keycloak-based)
```sql
CREATE TABLE user_profiles (
    keycloak_id UUID PRIMARY KEY,
    username VARCHAR(128) UNIQUE NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    quota BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Legacy Users Table
The original `users` table with `password_hash` is preserved but **not used**. All authentication is handled by Keycloak.

### MinIO Object Storage

This application uses **MinIO** for file storage instead of traditional filesystem storage. This provides:

**Benefits**:
- ✅ **Scalability**: Horizontal scaling across multiple nodes
- ✅ **S3 Compatibility**: Industry-standard API (boto3/minio libraries)
- ✅ **Cloud-Ready**: Mirrors real cloud providers (AWS S3, Azure Blob, GCP)
- ✅ **Multi-tenancy**: Built-in access control and user isolation
- ✅ **Durability**: Erasure coding and bit-rot protection
- ✅ **Container-friendly**: No volume mounts needed for file storage

**Storage Layout**:
```
MinIO Bucket: user-files/
├── alice/
│   ├── document.pdf
│   └── photos/image.jpg
├── bob/
│   └── data.csv
└── .bin/
    └── alice_20251125_123456_document.pdf  # Deleted files
```

**Configuration**:
- Endpoint: `minio:9000` (internal), `localhost:9000` (external)
- Console: `localhost:9001`
- Bucket: `user-files`
- Credentials managed via environment variables

The Flask backend uses the `minio` Python client to interact with MinIO using S3-compatible APIs.

## 🏗️ Database Initialization

The database and users are created separately from the Flask application (real-world scenario):

1. **Database init script**: `be_flask/db_init/001_create_users.sql`
   - Auto-generated by Vault init script
   - Contains hashed passwords from Vault
   - Executed by PostgreSQL on first startup

2. **Flask application**: Only connects to existing database
   - Does NOT create tables or users
   - Assumes database is pre-configured
   - Matches production deployment patterns

To regenerate the database init script with updated passwords:
```bash
cd vault/scripts
./generate-db-init.sh
```

Then reset the database:
```bash
docker compose down -v
docker compose up -d
```

## 🔧 Management Tasks

### Unseal Vault After Restart

Vault seals itself when the container restarts for security:

```bash
cd ../vault-infrastructure/scripts
./unseal-vault.sh
cd ../../4_three_tier_app
```

### Access MinIO Console

View and manage user files in the MinIO web console:

```bash
# Access at: http://localhost:9001
# Default credentials: minioadmin / minioadmin
```

MinIO provides:
- Web-based file browser
- Bucket management
- Access policy configuration
- Monitoring and metrics

### Rotate AppRole Credentials

```bash
cd vault/scripts
./rotate-secret-id.sh

# Update .env with new VAULT_SECRET_ID
docker compose restart backend
```

### Stop All Services

```bash
# Stop application
docker compose down

# Stop shared Vault (⚠️ affects all applications using it)
cd ../vault-infrastructure
docker compose down
```

### View Secrets

```bash
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=$(jq -r '.root_token' vault/scripts/vault-keys.json)

vault kv get secret/app/flask
vault kv get secret/database/postgres
```

### Update Application Secrets

```bash
# Update JWT signing key
vault kv patch secret/app/flask jwt_secret="new-secure-key"

# Restart to apply
docker compose restart backend
```

## 🛠️ Development vs Production

### Development Mode

For development without Vault:

```bash
# Set environment variables directly
export FLASK_ENV=development
export DATABASE_URL=postgresql://admin:password123@localhost:5432/postgres_db
export SECRET_KEY=dev-secret-key

# Start services
docker compose up -d
```

The application gracefully falls back to environment variables if Vault is unavailable.

### Production Mode

Production requires Vault integration:

1. Deploy Vault on separate infrastructure
2. Enable TLS for Vault
3. Use proper secret rotation policies
4. Implement monitoring and alerting
5. Regular backups of vault-keys.json
6. Use cloud KMS for auto-unsealing

See [VAULT_INTEGRATION.md](VAULT_INTEGRATION.md) for production guidelines.

## 📊 Project Structure

```
.
├── docker-compose.yaml             # Application stack (Apache, Flask, PostgreSQL, MinIO)
├── VAULT_INTEGRATION.md           # Vault documentation
├── .env.example                   # Configuration template
├── vault/
│   ├── config/
│   │   └── vault-config.hcl      # Vault server config
│   ├── policies/
│   │   ├── app-policy.hcl        # Application policy
│   │   └── admin-policy.hcl      # Admin policy
│   └── scripts/
│       ├── init-vault.sh         # Initialization script
│       ├── unseal-vault.sh       # Unseal helper
│       └── rotate-secret-id.sh   # Credential rotation
├── apache/                        # Frontend web server
├── be_flask/
│   └── src/
│       ├── vault_client.py       # Vault integration
│       ├── minio_client.py       # MinIO/S3 client
│       ├── config.py             # Config with Vault
│       ├── auth.py               # JWT auth with Vault
│       ├── utils_s3.py        # MinIO-based utilities
│       └── blueprints/
│           ├── files.py          # File operations (MinIO)
│           └── admin.py          # Admin endpoints
└── secrets/                       # Docker secrets (git-ignored)
    └── db_password.txt
```

## 🔍 Verification

Check that Vault integration is working:

```bash
# Backend should show Vault status
docker compose logs backend | grep "Vault"

# Should see:
# ✅ Vault integration enabled - secrets managed by Vault
# Successfully authenticated with Vault using AppRole  
# Using database configuration from Vault

# Check secret access
docker compose exec backend python3 -c "
from src.vault_client import get_vault_client
vc = get_vault_client()
print('Vault Available:', vc.is_available())
print('App Secrets:', list(vc.get_app_secrets().keys()))
"
```

## 🔒 Security Checklist

- ✅ All secrets in Vault (not in code/env files)
- ✅ AppRole authentication configured
- ✅ Vault policies limit application access
- ✅ Database credentials via Docker secrets
- ✅ JWT keys managed by Vault
- ✅ Regular secret rotation scheduled
- ✅ Vault data backed up securely
- ✅ TLS enabled for production
- ✅ Audit logging enabled
- ✅ Network segmentation implemented

## 🐛 Troubleshooting

### Vault Connection Issues

```bash
# Check Vault is running
docker compose -f docker-compose.vault.yaml ps

# Check Vault health
curl http://localhost:8200/v1/sys/health

# Unseal if needed
cd vault/scripts && ./unseal-vault.sh
```

### Application Can't Authenticate

```bash
# Verify credentials in .env
cat .env | grep VAULT

# Check backend logs
docker compose logs backend

# Rotate credentials if needed
cd vault/scripts && ./rotate-secret-id.sh
```

### Database Connection Issues

```bash
# Verify database password file exists
ls -la secrets/db_password.txt

# Check database logs
docker compose logs db

# Verify Vault has correct password
vault kv get secret/database/postgres
```

## 📖 Additional Resources

- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [AppRole Authentication](https://www.vaultproject.io/docs/auth/approle)
- [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/2.3.x/security/)

## 🤝 Contributing

When contributing:
1. Never commit secrets or credentials
2. Use Vault for all sensitive data  
3. Test with Vault integration enabled
4. Update documentation for config changes
5. Follow security best practices

## 📝 Notes

- `vault-keys.json` is critical - back it up securely
- Vault must be unsealed after every restart
- AppRole Secret ID should be rotated regularly
- Monitor Vault audit logs for security events
- Use separate Vault instances for dev/staging/prod

---

For detailed Vault setup, management, and troubleshooting, see **[VAULT_INTEGRATION.md](VAULT_INTEGRATION.md)**.
