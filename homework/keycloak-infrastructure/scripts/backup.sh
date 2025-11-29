#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Backup Keycloak Database${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if Keycloak is running
if ! docker ps | grep -q shared_keycloak_db; then
    echo -e "${RED}Error: Keycloak database is not running${NC}"
    echo "Start it with: docker compose up -d"
    exit 1
fi

# Create backup directory
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}Creating database backup...${NC}"

# Backup database
docker exec shared_keycloak_db pg_dump -U keycloak keycloak > "$BACKUP_DIR/keycloak_backup.sql"

echo -e "${GREEN}✓ Database backup created: $BACKUP_DIR/keycloak_backup.sql${NC}"

# Backup secrets
echo -e "${YELLOW}Backing up secrets...${NC}"
cp -r secrets "$BACKUP_DIR/"
echo -e "${GREEN}✓ Secrets backed up${NC}"

# Create backup info file
cat > "$BACKUP_DIR/backup_info.txt" << EOF
Keycloak Backup Information
===========================
Date: $(date)
Hostname: $(hostname)
Keycloak Version: $(docker exec shared-keycloak-server /opt/keycloak/bin/kc.sh --version 2>/dev/null || echo "Unknown")

Files:
- keycloak_backup.sql: PostgreSQL database dump
- secrets/: Credential files

Restore Instructions:
1. Stop Keycloak: docker compose down
2. Restore database:
   docker compose up -d keycloak_db
   cat keycloak_backup.sql | docker exec -i shared_keycloak_db psql -U keycloak keycloak
3. Restore secrets: cp -r secrets/* ../secrets/
4. Start Keycloak: docker compose up -d
EOF

echo -e "${GREEN}✓ Backup info created${NC}"
echo ""
echo -e "${GREEN}Backup completed successfully!${NC}"
echo "Location: $BACKUP_DIR"
echo ""
