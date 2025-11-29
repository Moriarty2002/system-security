#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Keycloak Infrastructure Initialization  ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Navigate to script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

# Create secrets directory if it doesn't exist
mkdir -p secrets

# Check if secrets already exist
if [ -f "secrets/db_password.txt" ] && [ -f "secrets/admin_password.txt" ]; then
    echo -e "${YELLOW}Secrets already exist!${NC}"
    echo ""
    read -p "Do you want to regenerate secrets? This will BREAK existing Keycloak data! (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Using existing secrets.${NC}"
        echo ""
        echo "Admin credentials:"
        echo "  Username: $(cat secrets/admin_username.txt)"
        echo "  Password: $(cat secrets/admin_password.txt)"
        echo ""
        exit 0
    fi
fi

echo -e "${YELLOW}Generating secure random passwords...${NC}"

# Generate database password
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo -n "$DB_PASSWORD" > secrets/db_password.txt
echo -e "${GREEN}✓ Database password generated${NC}"

# Generate admin credentials
ADMIN_USERNAME="admin"
ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo -n "$ADMIN_USERNAME" > secrets/admin_username.txt
echo -n "$ADMIN_PASSWORD" > secrets/admin_password.txt
echo -e "${GREEN}✓ Admin credentials generated${NC}"

# Set restrictive permissions
chmod 600 secrets/*.txt
echo -e "${GREEN}✓ Secrets file permissions set${NC}"

# Create .gitignore for secrets
cat > secrets/.gitignore << 'EOF'
# Ignore all secrets
*.txt
!.gitignore
EOF
echo -e "${GREEN}✓ Created .gitignore for secrets${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Keycloak Infrastructure Ready!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${YELLOW}Admin Credentials:${NC}"
echo "  Username: ${ADMIN_USERNAME}"
echo "  Password: ${ADMIN_PASSWORD}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Save these credentials securely!${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Start Keycloak infrastructure:"
echo "     ${GREEN}docker compose up -d${NC}"
echo ""
echo "  2. Wait for startup (about 60 seconds):"
echo "     ${GREEN}docker compose logs -f keycloak${NC}"
echo ""
echo "  3. Access Admin Console:"
echo "     ${GREEN}http://localhost:8080${NC}"
echo ""
echo "  4. Configure realm and clients (see README.md)"
echo ""
