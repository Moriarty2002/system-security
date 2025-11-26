#!/bin/bash
# Quick setup script for LDAP-integrated application
# This script sets up Vault, configures LDAP secrets, and starts the application

set -e

echo "🚀 Starting LDAP-integrated application setup..."
echo ""

# Get the parent directory (4_three_tier_app)
PARENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PARENT_DIR"

# Check if we're in the right directory
if [ ! -f "docker-compose.yaml" ]; then
    echo "❌ Error: docker-compose.yaml not found"
    echo "Please run this script from the 4_three_tier_app directory"
    exit 1
fi

# Step 1: Check if Vault is running
echo "📋 Step 1: Checking Vault infrastructure..."
if ! docker ps | grep -q shared_vault_server; then
    echo "⚠️  Vault server not running. Please start vault-infrastructure first:"
    echo "   cd ../vault-infrastructure"
    echo "   docker compose up -d"
    echo "   ./scripts/init-vault.sh"
    echo "   ./scripts/unseal-vault.sh"
    exit 1
fi
echo "✅ Vault server is running"
echo ""

# Step 2: Configure LDAP secrets in Vault
echo "📋 Step 2: Configuring LDAP secrets in Vault..."

# Retrieve Vault token from vault-keys.json
VAULT_KEYS_FILE="$PARENT_DIR/../vault-infrastructure/scripts/vault-keys.json"
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo "❌ Error: Vault keys file not found at $VAULT_KEYS_FILE"
    echo "   Please run the main setup first: cd $PARENT_DIR && ./setup.sh"
    exit 1
fi

export VAULT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE" 2>/dev/null)
if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
    echo "❌ Error: Could not retrieve Vault root token"
    echo "   Please ensure Vault is initialized and vault-keys.json exists"
    exit 1
fi

echo "🔑 Using Vault token from $VAULT_KEYS_FILE"

chmod +x vault/scripts/setup-vault-ldap.sh
./vault/scripts/setup-vault-ldap.sh
echo ""

# Step 3: Set up AppRole credentials for backend
echo "📋 Step 3: Setting up AppRole authentication..."
if [ ! -f "vault/scripts/approle-credentials.txt" ]; then
    echo "⚠️  AppRole credentials not found. Run setup-vault-app.sh first:"
    echo "   cd vault/scripts"
    echo "   ./setup-vault-app.sh"
    exit 1
fi
echo "✅ AppRole credentials exist"
echo ""

# Step 4: Check .env file
echo "📋 Step 4: Checking environment configuration..."
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cat > .env << 'EOF'
# Vault Configuration (shared infrastructure)
VAULT_ADDR=https://shared_vault_server:8200
VAULT_ROLE_ID=
VAULT_SECRET_ID=
VAULT_SECRET_ID=
APACHE_VAULT_AUTH_PATH=approle
PKI_ENGINE=pki_int
PKI_ROLE=apache-role

# Application Configuration
FLASK_ENV=development

# Database Configuration (admin user for initialization)
POSTGRES_USER=postgres
POSTGRES_DB=mes_local_cloud
POSTGRES_APP_USER=app_user
POSTGRES_APP_PASSWORD=will_be_rotated_by_vault

# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
EOF
    echo "⚠️  Please edit .env file and add VAULT_ROLE_ID and VAULT_SECRET_ID"
    echo "   Get them from: vault/scripts/approle-credentials.txt"
    exit 1
fi
echo "✅ .env file exists"
echo ""

# Step 5: Clean and start LDAP
echo "📋 Step 5: Preparing LDAP server..."
echo "Stopping LDAP container if running..."
docker-compose down ldap 2>/dev/null || true
echo "Removing old LDAP volumes..."
docker volume rm 4_three_tier_app_ldap_data 4_three_tier_app_ldap_config 2>/dev/null || true
echo "Starting LDAP with fresh configuration..."
docker-compose up -d ldap
echo ""

# Step 6: Start other application services
echo "📋 Step 6: Starting application services..."
docker-compose up -d
echo ""

# Step 7: Wait for services to be ready
echo "📋 Step 7: Waiting for services to be ready..."
echo "Waiting for LDAP server to initialize..."
sleep 10

# Check if services are healthy
echo "Checking service health..."
docker-compose ps
echo ""

# Step 8: Test LDAP connection
echo "📋 Step 8: Testing LDAP connectivity..."
docker exec ldap_server ldapsearch -x -H ldap://localhost \
    -b "dc=cloud,dc=mes" \
    -D "cn=admin,dc=cloud,dc=mes" \
    -w admin \
    "(objectClass=organizationalUnit)" dn 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ LDAP server is responding"
else
    echo "⚠️  LDAP server connection issues"
fi
echo ""

# Step 9: Display test credentials
echo "🎉 Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Default Test Credentials:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Admin User:"
echo "  Username: admin"
echo "  Password: admin"
echo "  Role: admin"
echo ""
echo "Regular User:"
echo "  Username: alice"
echo "  Password: alice"
echo "  Role: user"
echo ""
echo "Moderator:"
echo "  Username: moderator"
echo "  Password: moderator"
echo "  Role: moderator"
echo ""
echo "⚠️  Change these passwords in production!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Access Points:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Web Application: https://localhost"
echo "MinIO Console: http://localhost:9001"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Test Authentication:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "curl -X POST http://localhost/auth/login \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"username\": \"admin\", \"password\": \"admin\"}'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 Documentation:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "LDAP Integration Guide: LDAP_INTEGRATION.md"
echo "LDIF Customization Guide: ldap/LDIF_CUSTOMIZATION_GUIDE.md"
echo "Changes Summary: LDAP_CHANGES_SUMMARY.md"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
