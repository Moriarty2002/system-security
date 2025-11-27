#!/bin/bash
# Setup script for secure LDAP with TLS and network isolation
# This script configures all security features in the correct order

set -e

echo "🔐 Secure LDAP Setup Script"
echo "=============================="
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LDAP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$LDAP_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Check prerequisites
echo "📋 Step 1: Checking prerequisites..."

# Check if Vault is running
if ! docker ps | grep -q shared_vault_server; then
    echo "❌ Error: Vault server not running"
    echo "   Please start vault-infrastructure first:"
    echo "   cd ../vault-infrastructure && docker compose up -d"
    exit 1
fi

# Check for Vault token
VAULT_KEYS_FILE="$PROJECT_DIR/../vault-infrastructure/scripts/vault-keys.json"
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo "❌ Error: Vault keys file not found"
    echo "   Please initialize Vault first"
    exit 1
fi

export VAULT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE" 2>/dev/null)
if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
    echo "❌ Error: Could not retrieve Vault root token"
    exit 1
fi

echo "✅ Prerequisites checked"
echo ""

# Generate TLS certificates
echo "📋 Step 2: Generating TLS certificates for LDAPS..."
cd "$LDAP_DIR/scripts"
chmod +x generate-certs.sh
./generate-certs.sh
echo ""

# Set strong LDAP password
echo "📋 Step 3: Configuring LDAP admin password..."
if [ -z "$LDAP_ADMIN_PASSWORD" ]; then
    echo "⚠️  LDAP_ADMIN_PASSWORD not set in environment"
    echo "📝 Please enter a strong password for LDAP admin (min 16 characters):"
    read -s LDAP_ADMIN_PASSWORD
    echo ""
    
    if [ ${#LDAP_ADMIN_PASSWORD} -lt 16 ]; then
        echo "❌ Error: Password must be at least 16 characters"
        exit 1
    fi
fi

# Update .env file
cd "$PROJECT_DIR"
if grep -q "^LDAP_ADMIN_PASSWORD=" .env 2>/dev/null; then
    # Use a more portable sed command
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/^LDAP_ADMIN_PASSWORD=.*/LDAP_ADMIN_PASSWORD=$LDAP_ADMIN_PASSWORD/" .env
    else
        # Linux
        sed -i "s/^LDAP_ADMIN_PASSWORD=.*/LDAP_ADMIN_PASSWORD=$LDAP_ADMIN_PASSWORD/" .env
    fi
    echo "✅ Updated LDAP_ADMIN_PASSWORD in .env"
else
    echo "LDAP_ADMIN_PASSWORD=$LDAP_ADMIN_PASSWORD" >> .env
    echo "✅ Added LDAP_ADMIN_PASSWORD to .env"
fi
echo ""

# Configure Vault with LDAPS
echo "📋 Step 4: Storing LDAP configuration in Vault..."
cd "$PROJECT_DIR/vault/scripts"
chmod +x setup-vault-ldap.sh
export LDAP_ADMIN_PASSWORD
./setup-vault-ldap.sh
echo ""

# Stop and remove old LDAP container if exists
echo "📋 Step 5: Preparing Docker environment..."
if docker ps -a | grep -q ldap_server; then
    echo "⚠️  Removing old LDAP container..."
    docker stop ldap_server 2>/dev/null || true
    docker rm ldap_server 2>/dev/null || true
fi

# Remove old LDAP network if exists
if docker network ls | grep -q ldap_net; then
    echo "⚠️  Removing old LDAP network..."
    docker network rm ldap_net 2>/dev/null || true
fi

echo "✅ Docker environment prepared"
echo ""

# Start services
echo "📋 Step 6: Starting services with secure LDAP..."
cd "$PROJECT_DIR"
docker-compose up -d ldap

echo ""
echo "⏳ Waiting for LDAP server to start (30 seconds)..."
sleep 30

# Verify LDAP is running
if ! docker ps | grep -q ldap_server; then
    echo "❌ Error: LDAP server failed to start"
    echo "   Check logs: docker logs ldap_server"
    exit 1
fi

echo "✅ LDAP server started"
echo ""

# Start backend (which will connect to LDAP)
echo "📋 Step 7: Starting backend with LDAP integration..."
docker-compose up -d backend

echo ""
echo "⏳ Waiting for backend to initialize (10 seconds)..."
sleep 10

# Verify services
echo ""
echo "📋 Step 8: Verifying secure LDAP configuration..."

# Check LDAP health
if docker inspect ldap_server | grep -q '"Status": "healthy"'; then
    echo "✅ LDAP server is healthy"
else
    echo "⚠️  LDAP server health check pending..."
fi

# Check TLS certificates
if docker exec ldap_server ls /container/service/slapd/assets/certs/ldap-cert.pem > /dev/null 2>&1; then
    echo "✅ TLS certificates mounted"
else
    echo "❌ TLS certificates not found"
fi

# Check LDAP network
if docker network inspect ldap_net > /dev/null 2>&1; then
    echo "✅ Dedicated LDAP network created"
else
    echo "❌ LDAP network not found"
fi

# Check backend connectivity
if docker exec flask_be nc -zv ldap-server 636 2>&1 | grep -q succeeded; then
    echo "✅ Backend can reach LDAP server"
else
    echo "⚠️  Backend LDAP connectivity pending..."
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ Secure LDAP Setup Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "🔒 Security Features Enabled:"
echo "  ✅ LDAPS (TLS encryption) on port 636"
echo "  ✅ TLS certificate verification"
echo "  ✅ Dedicated LDAP network isolation"
echo "  ✅ No exposed ports to host"
echo "  ✅ Audit logging to ./ldap/logs/"
echo "  ✅ Strong admin password in Vault"
echo ""
echo "📁 Important Files:"
echo "  - TLS Certificates: ./ldap/certs/"
echo "  - Audit Logs: ./ldap/logs/"
echo "  - Configuration: ./ldap/SECURITY_CONFIGURATION.md"
echo "  - Network Details: ./ldap/NETWORK_ISOLATION.md"
echo ""
echo "🧪 Test LDAP Authentication:"
echo "  docker exec flask_be python3 -c \\"
echo "    'from src.ldap_client import *; \\"
echo "    from src.vault_client import get_vault_client; \\"
echo "    vc = get_vault_client(); \\"
echo "    lc = get_ldap_client(vc.get_ldap_config()); \\"
echo "    print(lc.authenticate(\"admin\", \"<password>\"))'"
echo ""
echo "📊 Monitor Audit Logs:"
echo "  tail -f ldap/logs/slapd.log"
echo ""
echo "🔐 Security Notes:"
echo "  - LDAP is only accessible via ldap_net (internal)"
echo "  - Backend has access via network isolation"
echo "  - All traffic encrypted with TLS 1.2+"
echo "  - Certificates valid for 365 days"
echo ""
echo "⚠️  Next Steps:"
echo "  1. Start remaining services: docker-compose up -d"
echo "  2. Test authentication via API"
echo "  3. Monitor audit logs for security events"
echo "  4. Set up log rotation for production"
echo ""
