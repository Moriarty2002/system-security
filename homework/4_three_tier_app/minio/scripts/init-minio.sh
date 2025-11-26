#!/bin/bash
# MinIO Initialization Script (Manual Execution from Host)
# This script creates a dedicated application user with least-privilege access
# and sets up proper bucket policies for the user-files bucket.
#
# Security Architecture:
# - Root user (MINIO_ROOT_USER): Used only for administration
# - App user (app-storage): Used by Flask backend, limited to user-files bucket
#
# Usage:
#   From host machine: ./minio/scripts/init-minio.sh
#   Requires: Docker, .env file with credentials (or uses defaults)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."

echo "======================================"
echo "MinIO Initialization Script"
echo "======================================"

# Load credentials from .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading credentials from .env file..."
    source "$PROJECT_ROOT/.env"
else
    echo "No .env file found, using default values..."
fi

# Set defaults if not provided
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
MINIO_APP_USER="${MINIO_APP_USER:-app-storage}"
MINIO_APP_PASSWORD="${MINIO_APP_PASSWORD:-app-minio-psw}"
MINIO_BUCKET="${MINIO_BUCKET:-user-files}"

echo "Configuration:"
echo "  Root User: $MINIO_ROOT_USER"
echo "  App User: $MINIO_APP_USER"
echo "  Bucket: $MINIO_BUCKET"
echo ""

# Check if MinIO container is running
echo "Checking MinIO container status..."
if ! docker ps --format '{{.Names}}' | grep -q '^minio_storage$'; then
    echo "❌ Error: MinIO container 'minio_storage' is not running"
    echo ""
    echo "Please start MinIO first:"
    echo "  cd $PROJECT_ROOT"
    echo "  docker compose up -d minio"
    echo ""
    echo "Or if you don't have .env file, create it with:"
    echo "  echo 'MINIO_ROOT_USER=minioadmin' > .env"
    echo "  echo 'MINIO_ROOT_PASSWORD=minioadmin' >> .env"
    exit 1
fi

echo "✓ MinIO container is running"

# Detect if we're connecting from inside Docker network or from host
# Try Docker network first, fall back to localhost
MINIO_ENDPOINT="minio:9000"
NETWORK_NAME="4_three_tier_app_app_net"

# Check if network exists
if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}$"; then
    echo "⚠️  Warning: Network '$NETWORK_NAME' not found, using host networking"
    MINIO_ENDPOINT="localhost:9000"
    NETWORK_FLAG="--network host"
else
    NETWORK_FLAG="--network $NETWORK_NAME"
fi

echo "  Endpoint: $MINIO_ENDPOINT"

# Set up MC host environment variable for all commands
export MC_HOST_myminio="http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@$MINIO_ENDPOINT"

# Function to run mc commands via Docker
mc_run() {
    docker run --rm $NETWORK_FLAG \
      -e MC_HOST_myminio="$MC_HOST_myminio" \
      minio/mc "$@"
}

# Wait for MinIO to be ready
echo "Waiting for MinIO API to be ready..."
RETRIES=15
COUNT=0
until mc_run admin info myminio >/dev/null 2>&1; do
    COUNT=$((COUNT + 1))
    if [ $COUNT -ge $RETRIES ]; then
        echo "❌ Error: MinIO did not become ready in time"
        echo ""
        echo "Troubleshooting:"
        echo "  1. Check MinIO container logs:"
        echo "     docker logs minio_storage"
        echo ""
        echo "  2. Check if MinIO ports are accessible:"
        echo "     curl -I http://localhost:9000"
        echo ""
        echo "  3. Verify credentials match .env file or defaults"
        exit 1
    fi
    echo "MinIO not ready yet, waiting... ($COUNT/$RETRIES)"
    sleep 2
done

echo "✓ MinIO is ready"

# Create bucket if it doesn't exist
echo "Creating bucket: $MINIO_BUCKET"
if mc_run ls myminio/"$MINIO_BUCKET" 2>/dev/null; then
    echo "✓ Bucket '$MINIO_BUCKET' already exists"
else
    mc_run mb myminio/"$MINIO_BUCKET"
    echo "✓ Bucket '$MINIO_BUCKET' created"
fi

# Create application user with secure credentials
echo "Creating application user '$MINIO_APP_USER'..."

# Check if user already exists (mc admin user info returns 0 if exists)
if mc_run admin user info myminio "$MINIO_APP_USER" 2>/dev/null; then
    echo "✓ User '$MINIO_APP_USER' already exists, updating credentials..."
    mc_run admin user remove myminio "$MINIO_APP_USER" 2>/dev/null || true
fi

# Create the user
mc_run admin user add myminio "$MINIO_APP_USER" "$MINIO_APP_PASSWORD"
echo "✓ User '$MINIO_APP_USER' created"

# Create policy for the application user (least privilege)
POLICY_FILE="/tmp/app-storage-policy-$$.json"
cat > "$POLICY_FILE" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::$MINIO_BUCKET",
        "arn:aws:s3:::$MINIO_BUCKET/*"
      ]
    }
  ]
}
EOF

# Apply policy
echo "Creating and applying least-privilege policy..."
docker run --rm -v "$POLICY_FILE:/policy.json" \
  --network 4_three_tier_app_app_net \
  -e MC_HOST_myminio="$MC_HOST_myminio" \
  minio/mc admin policy create myminio app-storage-policy /policy.json 2>/dev/null || \
docker run --rm -v "$POLICY_FILE:/policy.json" \
  --network 4_three_tier_app_app_net \
  -e MC_HOST_myminio="$MC_HOST_myminio" \
  minio/mc admin policy update myminio app-storage-policy /policy.json

# Attach policy to user
mc_run admin policy attach myminio app-storage-policy --user="$MINIO_APP_USER"

echo "✓ Policy 'app-storage-policy' created and attached to user"

# Clean up
rm "$POLICY_FILE"

echo ""
echo "======================================"
echo "MinIO Initialization Complete"
echo "======================================"
echo "Root User: $MINIO_ROOT_USER (admin only)"
echo "App User:  $MINIO_APP_USER (application use)"
echo "Bucket:    $MINIO_BUCKET"
echo "Policy:    app-storage-policy (read/write on bucket only)"
echo "======================================"
echo ""
echo "Security Notes:"
echo "- Root credentials should NEVER be used by the application"
echo "- App user has NO admin capabilities"
echo "- App user can ONLY access the '$MINIO_BUCKET' bucket"
echo "- Credentials are stored in Vault at: secret/mes_local_cloud/minio"
echo "======================================"
