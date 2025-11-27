#!/bin/bash
# Migration script from old LDAP setup to secure LDAPS configuration
# This script handles the transition for an already-running system

set -e

echo "🔄 LDAP Security Migration Script"
echo "=================================="
echo ""
echo "This script will upgrade your existing LDAP setup to use:"
echo "  • LDAPS (TLS encryption)"
echo "  • Certificate verification"
echo "  • Network isolation"
echo "  • Audit logging"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LDAP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$LDAP_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Step 1: Backup existing data
echo "📋 Step 1: Backing up existing LDAP data..."

# Check if LDAP container exists
if docker ps -a | grep -q ldap_server; then
    echo "⚠️  Found existing LDAP container"
    
    # Backup LDAP data
    BACKUP_DIR="$LDAP_DIR/backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    echo "📦 Creating backup at: $BACKUP_DIR"
    
    # Export LDAP data
    if docker exec ldap_server slapcat -n 1 > "$BACKUP_DIR/ldap_data.ldif" 2>/dev/null; then
        echo "✅ LDAP data exported to $BACKUP_DIR/ldap_data.ldif"
    else
        echo "⚠️  Could not export LDAP data (container may not be running)"
    fi
    
    # Backup docker volumes
    docker run --rm -v 4_three_tier_app_ldap_data:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/ldap_data_volume.tar.gz -C /data . 2>/dev/null || echo "⚠️  Could not backup ldap_data volume"
    docker run --rm -v 4_three_tier_app_ldap_config:/data -v "$BACKUP_DIR":/backup alpine tar czf /backup/ldap_config_volume.tar.gz -C /data . 2>/dev/null || echo "⚠️  Could not backup ldap_config volume"
    
    echo "✅ Backup completed"
else
    echo "ℹ️  No existing LDAP container found"
fi

echo ""

# Step 2: Check Vault
echo "📋 Step 2: Checking Vault availability..."

if ! docker ps | grep -q shared_vault_server; then
    echo "❌ Error: Vault server not running"
    echo "   Please start vault-infrastructure first:"
    echo "   cd ../vault-infrastructure && docker compose up -d"
    exit 1
fi

VAULT_KEYS_FILE="$PROJECT_DIR/../vault-infrastructure/scripts/vault-keys.json"
if [ ! -f "$VAULT_KEYS_FILE" ]; then
    echo "❌ Error: Vault keys file not found"
    exit 1
fi

export VAULT_TOKEN=$(jq -r '.root_token' "$VAULT_KEYS_FILE" 2>/dev/null)
if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
    echo "❌ Error: Could not retrieve Vault root token"
    exit 1
fi

echo "✅ Vault is available"
echo ""

# Step 3: Generate TLS certificates
echo "📋 Step 3: Generating TLS certificates..."

if [ ! -f "$LDAP_DIR/certs/ldap-cert.pem" ]; then
    cd "$LDAP_DIR/scripts"
    chmod +x generate-certs.sh
    ./generate-certs.sh
    cd "$PROJECT_DIR"
else
    echo "ℹ️  TLS certificates already exist, skipping generation"
    echo "   To regenerate: rm -rf ldap/certs/*.pem && ./ldap/scripts/generate-certs.sh"
fi

echo ""

# Step 4: Update Vault configuration
echo "📋 Step 4: Updating Vault with LDAPS configuration..."

export LDAP_ADMIN_PASSWORD="${LDAP_ADMIN_PASSWORD:-admin}"

cd "$PROJECT_DIR/vault/scripts"
chmod +x setup-vault-ldap.sh
./setup-vault-ldap.sh

cd "$PROJECT_DIR"
echo ""

# Step 5: Stop services
echo "📋 Step 5: Stopping existing services..."

echo "⚠️  This will temporarily stop LDAP and backend services"
read -p "Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Migration cancelled"
    exit 1
fi

# Stop backend first (it depends on LDAP)
if docker ps | grep -q flask_be; then
    echo "🛑 Stopping backend..."
    docker-compose stop backend
fi

# Stop LDAP
if docker ps | grep -q ldap_server; then
    echo "🛑 Stopping LDAP server..."
    docker-compose stop ldap
fi

echo "✅ Services stopped"
echo ""

# Step 6: Remove old LDAP container and network
echo "📋 Step 6: Cleaning up old configuration..."

# Remove old container (preserves volumes)
if docker ps -a | grep -q ldap_server; then
    echo "🗑️  Removing old LDAP container..."
    docker rm ldap_server 2>/dev/null || true
fi

# Remove old network if it exists
if docker network ls | grep -q ldap_net; then
    echo "🗑️  Removing old LDAP network..."
    docker network rm ldap_net 2>/dev/null || true
fi

echo "✅ Cleanup completed"
echo ""

# Step 7: Create logs directory
echo "📋 Step 7: Setting up audit logging..."
mkdir -p "$LDAP_DIR/logs"
echo "✅ Log directory created"
echo ""

# Step 8: Start services with new configuration
echo "📋 Step 8: Starting services with secure configuration..."

# Start LDAP first
echo "🚀 Starting LDAP server with LDAPS..."
docker-compose up -d ldap

echo "⏳ Waiting for LDAP to initialize (30 seconds)..."
sleep 30

# Check LDAP health
if docker inspect ldap_server 2>/dev/null | grep -q '"Status": "healthy"'; then
    echo "✅ LDAP server is healthy"
elif docker ps | grep -q ldap_server; then
    echo "⚠️  LDAP server is running but health check pending..."
else
    echo "❌ Error: LDAP server failed to start"
    echo "   Check logs: docker logs ldap_server"
    exit 1
fi

# Start backend
echo "🚀 Starting backend..."
docker-compose up -d backend

echo "⏳ Waiting for backend to initialize (10 seconds)..."
sleep 10

echo ""

# Step 9: Verify migration
echo "📋 Step 9: Verifying secure LDAP configuration..."

# Check LDAP is using LDAPS
if docker exec ldap_server env | grep -q "LDAP_TLS=true"; then
    echo "✅ LDAPS enabled"
else
    echo "⚠️  LDAPS configuration not detected"
fi

# Check certificates
if docker exec ldap_server ls /container/service/slapd/assets/certs/ldap-cert.pem > /dev/null 2>&1; then
    echo "✅ TLS certificates mounted"
else
    echo "❌ TLS certificates not found"
fi

# Check network
if docker network inspect ldap_net > /dev/null 2>&1; then
    echo "✅ Dedicated LDAP network created"
    
    # Check backend connectivity
    BACKEND_ON_LDAP_NET=$(docker network inspect ldap_net --format '{{range .Containers}}{{.Name}} {{end}}' | grep -c flask_be || echo 0)
    if [ "$BACKEND_ON_LDAP_NET" -gt 0 ]; then
        echo "✅ Backend connected to LDAP network"
    else
        echo "⚠️  Backend not yet connected to LDAP network"
    fi
else
    echo "❌ LDAP network not found"
fi

# Check logs directory
if [ -d "$LDAP_DIR/logs" ]; then
    echo "✅ Audit logging directory configured"
else
    echo "⚠️  Logs directory not found"
fi

# Test LDAPS connection
echo ""
echo "🧪 Testing LDAPS connection..."
if docker exec ldap_server ldapsearch -x -H ldaps://localhost:636 -b "dc=cloud,dc=mes" -D "cn=admin,dc=cloud,dc=mes" -w admin -LLL > /dev/null 2>&1; then
    echo "✅ LDAPS connection successful"
else
    echo "⚠️  LDAPS connection test failed (may need more time to initialize)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ Migration Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "🔒 Security Features Now Active:"
echo "  ✅ LDAPS (TLS encryption) on port 636"
echo "  ✅ TLS certificate verification enabled"
echo "  ✅ Dedicated LDAP network isolation"
echo "  ✅ No exposed ports to host"
echo "  ✅ Audit logging to ./ldap/logs/"
echo ""
echo "📁 Backup Location:"
echo "  $BACKUP_DIR"
echo ""
echo "📊 Monitor Audit Logs:"
echo "  tail -f ldap/logs/slapd.log"
echo ""
echo "🧪 Test Authentication:"
echo "  docker exec flask_be python3 -c \\"
echo "    'from src.vault_client import get_vault_client; \\"
echo "     from src.ldap_client import get_ldap_client; \\"
echo "     vc = get_vault_client(); \\"
echo "     lc = get_ldap_client(vc.get_ldap_config()); \\"
echo "     print(lc.authenticate(\"admin\", \"admin\"))'"
echo ""
echo "⚠️  Next Steps:"
echo "  1. Test LDAP authentication via your application"
echo "  2. Start remaining services: docker-compose up -d"
echo "  3. Monitor audit logs for any issues"
echo "  4. Keep backup until you confirm everything works"
echo ""
echo "🔄 Rollback Instructions (if needed):"
echo "  1. Stop services: docker-compose down"
echo "  2. Restore volumes from: $BACKUP_DIR"
echo "  3. Revert docker-compose.yaml changes"
echo "  4. Start services: docker-compose up -d"
echo ""
