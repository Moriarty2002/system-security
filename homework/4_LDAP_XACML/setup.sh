#!/bin/bash
# Complete Setup and Startup Script for Vault-Integrated Application
#
# This script provides a one-command setup for the entire application stack.
# It handles Vault initialization, secret generation, and application startup.
#
# Usage: ./setup.sh [--reset]
#
# Options:
#   --reset    Remove all existing data and start fresh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESET=false

# Parse arguments
if [[ "$1" == "--reset" ]]; then
    RESET=true
fi

echo "==========================================="
echo "Secure File Storage - Complete Setup"
echo "==========================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "❌ jq is not installed (required for JSON processing)"
    echo "   Install with: sudo apt install jq (Ubuntu) or brew install jq (macOS)"
    exit 1
fi

echo "✅ All prerequisites met"
echo ""

# Reset if requested
if [ "$RESET" = true ]; then
    echo "⚠️  RESET MODE: Removing all existing data..."
    echo ""
    read -p "Are you sure? This will delete all data and secrets. (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Reset cancelled"
        exit 0
    fi
    
    echo "Stopping all services..."
    docker compose down -v 2>/dev/null || true
    docker compose -f docker-compose.vault.yaml down -v 2>/dev/null || true
    
    echo "Removing generated files..."
    rm -f .env
    rm -rf secrets/
    rm -f vault/scripts/vault-keys.json
    rm -f vault/scripts/approle-credentials.txt
    
    echo "✅ Reset complete"
    echo ""
fi

# Step 1: Start Vault
echo "==========================================="
echo "Step 1: Starting Vault Infrastructure"
echo "==========================================="
echo ""

# Check if Vault is already running
if docker ps | grep -q vault_server; then
    echo "ℹ️  Vault server is already running"
    
    # Check if it's initialized
    if [ -f "$SCRIPT_DIR/vault/scripts/vault-keys.json" ]; then
        echo "ℹ️  Vault is already initialized"
        
        # Try to unseal
        echo "Checking Vault seal status..."
        export VAULT_ADDR=http://localhost:8200
        if vault status 2>&1 | grep -q "Sealed.*true"; then
            echo "Vault is sealed, unsealing..."
            cd vault/scripts
            ./unseal-vault.sh
            cd ../..
        else
            echo "✅ Vault is already unsealed"
        fi
    else
        echo "❌ Vault is running but not initialized"
        echo "Run the initialization manually: cd vault/scripts && ./init-vault.sh"
        exit 1
    fi
else
    echo "Starting Vault server..."
    docker compose -f docker-compose.vault.yaml up -d
    
    echo "Waiting for Vault to be ready..."
    sleep 10
    
    # Wait for Vault to be responsive
    MAX_RETRIES=30
    RETRY=0
    while [ $RETRY -lt $MAX_RETRIES ]; do
        if curl -s http://localhost:8200/v1/sys/health > /dev/null 2>&1; then
            echo "✅ Vault is ready"
            break
        fi
        RETRY=$((RETRY+1))
        echo "Waiting... ($RETRY/$MAX_RETRIES)"
        sleep 2
    done
    
    if [ $RETRY -eq $MAX_RETRIES ]; then
        echo "❌ Vault did not become ready in time"
        exit 1
    fi
    
    echo ""
    echo "==========================================="
    echo "Step 2: Initializing Vault"
    echo "==========================================="
    echo ""
    
    cd vault/scripts
    ./init-vault.sh
    cd ../..
fi

echo ""
echo "==========================================="
echo "Step 3: Verifying Configuration"
echo "==========================================="
echo ""

# Check that required files exist
if [ ! -f ".env" ]; then
    echo "❌ .env file not found"
    exit 1
fi

if [ ! -f "secrets/db_password.txt" ]; then
    echo "❌ secrets/db_password.txt not found"
    exit 1
fi

echo "✅ Configuration files verified"
echo ""

# Step 4: Start Application
echo "==========================================="
echo "Step 4: Starting Application Stack"
echo "==========================================="
echo ""

echo "Starting application services..."
docker compose up -d

echo "Waiting for services to be ready..."
sleep 5

# Wait for backend to be healthy
MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if docker compose ps | grep backend | grep -q "Up"; then
        echo "✅ Backend service is running"
        break
    fi
    RETRY=$((RETRY+1))
    echo "Waiting for backend... ($RETRY/$MAX_RETRIES)"
    sleep 2
done

# Wait for database to be healthy
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if docker compose ps | grep postgres_db | grep -q "healthy"; then
        echo "✅ Database is healthy"
        break
    fi
    RETRY=$((RETRY+1))
    echo "Waiting for database... ($RETRY/$MAX_RETRIES)"
    sleep 2
done

echo ""
echo "==========================================="
echo "Step 5: Verifying Vault Integration"
echo "==========================================="
echo ""

# Check backend logs for Vault integration
sleep 3
if docker compose logs backend 2>&1 | grep -q "Vault integration enabled"; then
    echo "✅ Backend successfully connected to Vault"
else
    echo "⚠️  Backend may not be connected to Vault"
    echo "    Check logs: docker compose logs backend"
fi

echo ""
echo "==========================================="
echo "🎉 Setup Complete!"
echo "==========================================="
echo ""
echo "📊 Service Status:"
docker compose ps
echo ""
echo "🌐 Access Points:"
echo "   - Application:  http://localhost or https://localhost"
echo "   - Vault UI:     http://localhost:8200"
echo "   - Backend API:  http://localhost:5000"
echo ""
echo "👤 Default Users (passwords from Vault):"
echo "   - admin / admin123"
echo "   - alice / alice123"
echo "   - moderator / moderator123"
echo ""
echo "🔑 Vault Access:"
VAULT_TOKEN=$(jq -r '.root_token' vault/scripts/vault-keys.json 2>/dev/null || echo "N/A")
echo "   - Root Token: $VAULT_TOKEN"
echo "   - Login at: http://localhost:8200"
echo ""
echo "📝 Useful Commands:"
echo "   - View logs:        docker compose logs -f"
echo "   - Stop services:    docker compose down"
echo "   - Restart backend:  docker compose restart backend"
echo "   - Unseal Vault:     cd vault/scripts && ./unseal-vault.sh"
echo ""
echo "📖 Documentation:"
echo "   - README.md - Quick start guide"
echo "   - VAULT_INTEGRATION.md - Detailed Vault documentation"
echo ""
echo "⚠️  IMPORTANT:"
echo "   - Keep vault/scripts/vault-keys.json secure and backed up"
echo "   - Vault must be unsealed after system restart"
echo "   - Never commit .env or secrets/ to version control"
echo ""
