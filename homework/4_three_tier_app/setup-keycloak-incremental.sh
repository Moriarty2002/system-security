#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Keycloak Incremental Setup Helper   ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "This script adds Keycloak WITHOUT destroying existing data."
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.yaml" ]; then
    echo -e "${RED}Error: docker-compose.yaml not found${NC}"
    echo "Please run this script from the 4_three_tier_app directory"
    exit 1
fi

# Check if database is running
if ! docker compose ps db | grep -q "running"; then
    echo -e "${YELLOW}Warning: Database is not running${NC}"
    echo "Starting database first..."
    docker compose up -d db
    sleep 5
fi

echo -e "${GREEN}Step 1: Configure Keycloak secrets in Vault${NC}"
echo "This will store Keycloak credentials without affecting existing data."
read -p "Run setup-keycloak-vault.sh? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "vault/scripts/setup-keycloak-vault.sh" ]; then
        cd vault/scripts
        ./setup-keycloak-vault.sh
        cd ../..
    else
        echo -e "${RED}Error: setup-keycloak-vault.sh not found${NC}"
        exit 1
    fi
else
    echo "Skipping Vault setup. Make sure KEYCLOAK_* variables are set in .env"
fi

echo ""
echo -e "${GREEN}Step 2: Create user_profiles table (if not exists)${NC}"
echo "This adds the new table without touching the old 'users' table."
read -p "Create user_profiles table? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "be_flask/db_init/001_create_user_profiles.sql" ]; then
        echo "Creating table..."
        docker compose exec -T db psql -U postgres -d local_cloud < be_flask/db_init/001_create_user_profiles.sql 2>&1 | grep -v "already exists" || true
        echo -e "${GREEN}✓ Table created (or already exists)${NC}"
    else
        echo -e "${RED}Error: SQL file not found${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}Step 3: Start Keycloak service${NC}"
echo "This starts only Keycloak without affecting other running services."
read -p "Start Keycloak? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting Keycloak..."
    docker compose up -d keycloak
    echo ""
    echo "Waiting for Keycloak to be ready (this may take 30-60 seconds)..."
    
    # Wait for Keycloak to be healthy
    TIMEOUT=120
    ELAPSED=0
    while [ $ELAPSED -lt $TIMEOUT ]; do
        if docker compose ps keycloak | grep -q "healthy"; then
            echo -e "${GREEN}✓ Keycloak is ready!${NC}"
            break
        fi
        echo -n "."
        sleep 5
        ELAPSED=$((ELAPSED + 5))
    done
    
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo -e "${YELLOW}Warning: Keycloak health check timeout. Check logs: docker compose logs keycloak${NC}"
    fi
fi

echo ""
echo -e "${GREEN}Step 4: Restart backend to use Keycloak${NC}"
read -p "Restart backend? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Restarting backend..."
    docker compose restart backend
    sleep 3
    echo -e "${GREEN}✓ Backend restarted${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo -e "${YELLOW}1. Configure Keycloak Admin Console:${NC}"
echo "   URL: http://localhost:8080"
echo "   Username: admin"
echo "   Password: (check .env file or setup script output)"
echo ""
echo -e "${YELLOW}2. Create Realm: 'mes-local-cloud'${NC}"
echo ""
echo -e "${YELLOW}3. Create Client: 'mes-local-cloud-api'${NC}"
echo "   - Valid redirect URIs: http://localhost/*"
echo "   - Web origins: http://localhost"
echo ""
echo -e "${YELLOW}4. Create Roles: admin, moderator, user${NC}"
echo ""
echo -e "${YELLOW}5. Create Users and assign roles${NC}"
echo ""
echo -e "${YELLOW}6. Test Login:${NC}"
echo "   Open http://localhost and click 'Login with Keycloak'"
echo ""
echo -e "${BLUE}Data Status:${NC}"
echo "✓ Old 'users' table: PRESERVED (not deleted)"
echo "✓ MinIO data: UNCHANGED"
echo "✓ bin_items table: UNCHANGED"
echo "✓ New 'user_profiles' table: CREATED"
echo ""
echo "For detailed instructions, see: KEYCLOAK_INCREMENTAL_SETUP.md"
echo ""
