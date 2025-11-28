# Secure File Storage Service with HashiCorp Vault and LDAP Authentication

A production-ready web application with enterprise-grade secrets management using HashiCorp Vault and centralized LDAP authentication.

## 🔐 Security Features

- **XACML Authorization**: Policy-based access control using XACML 3.0 standard
- **LDAP Authentication**: Centralized user authentication via OpenLDAP
- **No Password Storage**: Application never stores user passwords
- **HashiCorp Vault Integration**: All secrets (including LDAP credentials) managed by Vault
- **No Hardcoded Credentials**: Zero secrets in code or config files
- **AppRole Authentication**: Secure machine-to-machine authentication
- **JWT Token Security**: Signing keys rotated and managed by Vault
- **Database Security**: Credentials stored and rotated in Vault
- **MinIO Security**: Dedicated application user with bucket-only access
- **Docker Secrets**: Sensitive data passed via Docker secrets API
- **Network Isolation**: Separate networks for Vault and application
- **Fine-Grained Access Control**: XACML policies with attribute-based conditions
- **Least Privilege**: Minimal container capabilities and permissions

## 🏗️ Architecture

### Three-Tier Infrastructure

**1. Shared Vault Infrastructure** (Independent, at homework/vault-infrastructure/)
- HashiCorp Vault server
- Secrets storage and management
- Policy-based access control
- Audit logging
- **Shared by multiple applications**

**2. Application Stack** (This project: 4_three_tier_app)
- Apache HTTPS frontend
- Flask API backend
- **OpenLDAP authentication server**
- PostgreSQL database
- MinIO object storage (S3-compatible)
- Connects to shared Vault for secrets

**3. Authentication & Authorization Flow**
- User submits credentials to backend
- Backend authenticates against LDAP server
- LDAP verifies credentials and returns user info
- Backend queries LDAP for group membership (roles)
- Backend issues JWT token with user's role
- **XACML PDP evaluates access requests against policies**
- **XACML PEP enforces authorization decisions**
- Subsequent requests validated via JWT and XACML policies

This separation enables:
- ✅ Centralized authentication across multiple applications
- ✅ No password storage in application database
- ✅ Independent Vault lifecycle
- ✅ Multiple applications sharing the same Vault and LDAP
- ✅ Production deployment on separate hosts
- ✅ Enhanced security through isolation
- ✅ Real-world enterprise architecture
- ✅ Scalable object storage for user files

## 🚀 Quick Start with LDAP

### Prerequisites
- Shared Vault infrastructure running (see vault-infrastructure/)
- VAULT_TOKEN environment variable set

### Automated Setup (Recommended)

```bash
./setup.sh
```

This script will:
1. Start and initialize shared Vault infrastructure (if not running)
2. Configure application secrets in Vault
3. Configure LDAP authentication secrets
4. Start all services (Apache, Flask, PostgreSQL, LDAP, MinIO)
5. Verify all integrations
6. Display access information and credentials

**Alternative - LDAP-focused setup:**
```bash
cd ldap
./setup-ldap.sh
```
This assumes Vault is already set up and focuses on LDAP verification.

### Manual Setup

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
./init-vault.sh
cd ../../4_three_tier_app
```

**⚠️ IMPORTANT**: The script creates `vault-keys.json` with unseal keys in `../vault-infrastructure/scripts/`. **Keep this file secure and backed up!**

### Step 2: Configure This Application in Vault

```bash
# Configure application-specific secrets and policies
cd vault/scripts
./setup-vault-app.sh

# Configure LDAP secrets in Vault
./setup-vault-ldap.sh
cd ../..
```

These scripts:
- Create namespaced policies for this application
- Generate AppRole credentials
- Store secrets at `secret/mes_local_cloud/`
- Configure LDAP connection settings in Vault
- Create database initialization script

### Step 3: Reset Database (First Time Setup)

Since the database init script was just generated, you need to reset the database:

```bash
# Stop services and remove database volume
docker compose down -v
docker volume rm 4_three_tier_app_pg_data 2>/dev/null || true
docker volume rm 4_three_tier_app_ldap_data 2>/dev/null || true
docker volume rm 4_three_tier_app_ldap_config 2>/dev/null || true

# This ensures the init scripts run when services start
```

### Step 4: Start Application

```bash
# Start the application stack (from 4_three_tier_app directory)
docker compose up -d

# Verify Vault integration
docker compose logs backend | grep -E "Vault|LDAP"

# Expected output:
# ✅ LDAP client initialized - using LDAP authentication
# ✅ Vault integration enabled - secrets managed by Vault
```

### Step 5: Access the Application

- **Application**: https://localhost (or http://localhost)
- **Vault UI**: http://localhost:8200
- **MinIO Console**: http://localhost:9001 (credentials: minioadmin/minioadmin123)
- **API**: http://localhost:5000

**Default LDAP Users**:
- **admin** / admin (admin role)
- **alice** / alice (user role)
- **moderator** / moderator (moderator role)

⚠️ **Security**: Default passwords are set to username for ease of testing. Change these in production!

### Step 6: Test LDAP Authentication

```bash
# Test login
curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Response includes JWT token with role
```

## 📚 LDAP Documentation

- **[VAULT_INTEGRATION.md](VAULT_INTEGRATION.md)** - Complete Vault setup and management guide
- **[.env.example](.env.example)** - Environment configuration template

## 🗄️ Storage Architecture

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
│       ├── utils_minio.py        # MinIO-based utilities
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

- [XACML Integration Documentation](XACML_INTEGRATION.md) - **Complete guide to XACML authorization**
- [XACML Quick Reference](xacml/XACML_QUICK_REFERENCE.md) - **Quick access control matrix and test commands**
- [LDAP Integration Guide](LDAP_INTEGRATION.md) - Setup and management of LDAP authentication
- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [AppRole Authentication](https://www.vaultproject.io/docs/auth/approle)
- [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/2.3.x/security/)
- [OASIS XACML 3.0 Specification](http://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html)

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
