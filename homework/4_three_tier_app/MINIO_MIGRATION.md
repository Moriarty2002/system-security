# MinIO Storage Migration Guide

## Overview

This application has been migrated from filesystem-based storage to **MinIO object storage** (S3-compatible). This document explains the changes and benefits.

## Why MinIO?

### Problems with Filesystem Storage
- ❌ Doesn't scale horizontally (files stuck on one server)
- ❌ Lost when containers restart (without persistent volumes)
- ❌ Complex backup/recovery procedures
- ❌ Poor concurrent access handling
- ❌ Not cloud-native

### Benefits of MinIO
- ✅ **Scalability**: Horizontal scaling across multiple nodes
- ✅ **Cloud-Ready**: S3-compatible API used by AWS, Azure, GCP
- ✅ **Container-Friendly**: No volume mounts needed
- ✅ **Multi-Tenancy**: Built-in access control per user
- ✅ **Durability**: Erasure coding and bit-rot protection
- ✅ **Industry Standard**: Same API as AWS S3

## Architecture Changes

### Before (Filesystem)
```
Flask Backend
    ↓
Local Filesystem (/app/storage/)
    ├── alice/
    │   └── file.txt
    └── bob/
        └── data.csv
```

### After (MinIO)
```
Flask Backend
    ↓
MinIO Client (minio Python library)
    ↓
MinIO Server (S3-compatible)
    ↓
MinIO Bucket: user-files
    ├── alice/file.txt
    └── bob/data.csv
```

## Technical Changes

### 1. Docker Compose
Added MinIO service:
```yaml
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"  # API
      - "9001:9001"  # Web Console
```

### 2. Python Dependencies
Added to `requirements.txt`:
```
minio>=7.1.0
```

### 3. New Modules

**`src/minio_client.py`**
- MinIOClient class for S3 operations
- Handles upload, download, delete, list operations
- Namespace isolation per user

**`src/utils_minio.py`**
- Replaces filesystem-based utils
- MinIO-based implementations of file operations

### 4. Updated Code

**Upload Flow**:
```python
# Before (Filesystem)
file.save(os.path.join(user_dir, filename))

# After (MinIO)
minio_client.upload_file(
    username,
    file_path,
    file_stream,
    file_size,
    content_type
)
```

**Download Flow**:
```python
# Before (Filesystem)
send_from_directory(user_dir, filename)

# After (MinIO)
file_data = minio_client.download_file(username, file_path)
send_file(io.BytesIO(file_data), download_name=filename)
```

## Configuration

### Environment Variables
```bash
# MinIO endpoint (Docker internal)
MINIO_ENDPOINT=minio:9000

# Credentials
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Bucket name
MINIO_BUCKET=user-files

# Use SSL (false for development)
MINIO_USE_SSL=false
```

### Access MinIO Console
- URL: http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin`

## Storage Layout

### User Files
```
Bucket: user-files
├── alice/
│   ├── document.pdf
│   ├── photos/
│   │   └── image.jpg
│   └── data/
│       └── report.xlsx
├── bob/
│   └── readme.txt
└── .bin/
    ├── alice_20251125_123456_document.pdf
    └── bob_20251125_234567_readme.txt
```

### Object Naming Convention
- User files: `{username}/{path/to/file}`
- Bin files: `.bin/{username}_{timestamp}_{filename}`
- Directory markers: `{path}/.directory`

## API Compatibility

All REST APIs remain **100% compatible**. No frontend changes needed.

### Upload
```bash
POST /upload
Content-Type: multipart/form-data

file: <binary>
path: photos/  # optional subdirectory
```

### List Files
```bash
GET /files?path=photos/
→ Returns same JSON structure
```

### Download
```bash
GET /files/document.pdf?path=photos/
→ Returns file as before
```

### Delete (Move to Bin)
```bash
DELETE /files/document.pdf?path=photos/
→ Moves to MinIO .bin/ prefix
```

## Migration Steps

If you have existing data to migrate:

### 1. Export Existing Files (if needed)
```bash
# Before migration, backup filesystem storage
tar -czf storage_backup.tar.gz be_flask/storage/
```

### 2. Start MinIO
```bash
docker compose up -d minio
```

### 3. Upload Files to MinIO
```python
from minio import Minio
import os

client = Minio('localhost:9000',
    access_key='minioadmin',
    secret_key='minioadmin',
    secure=False
)

# Create bucket
if not client.bucket_exists('user-files'):
    client.make_bucket('user-files')

# Upload files
for root, dirs, files in os.walk('be_flask/storage/'):
    for file in files:
        local_path = os.path.join(root, file)
        # Calculate relative path from storage dir
        rel_path = os.path.relpath(local_path, 'be_flask/storage/')
        client.fput_object('user-files', rel_path, local_path)
```

### 4. Update Application
```bash
# Rebuild with new dependencies
docker compose build backend

# Restart with MinIO integration
docker compose up -d
```

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-mock

# Run tests
pytest tests/
```

### Local Development
```bash
# Start MinIO locally
docker run -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Set environment
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
export MINIO_BUCKET=user-files
export MINIO_USE_SSL=false

# Run Flask
python -m src.be
```

## Production Considerations

### 1. Security
```bash
# Use strong credentials
MINIO_ROOT_USER=<random-32-char>
MINIO_ROOT_PASSWORD=<random-64-char>

# Enable TLS
MINIO_USE_SSL=true

# Configure in Vault
vault kv put secret/mes_local_cloud/minio \
  access_key=<key> \
  secret_key=<secret>
```

### 2. High Availability
```yaml
# Use distributed MinIO (4+ nodes)
docker service create \
  --name minio \
  --replicas 4 \
  minio/minio server \
  http://minio-{1...4}/data
```

### 3. Backup Strategy
```bash
# Enable versioning
mc version enable myminio/user-files

# Setup replication
mc replicate add myminio/user-files \
  --remote-bucket backup-bucket \
  --priority 1
```

### 4. Monitoring
```bash
# Prometheus metrics
curl http://localhost:9000/minio/v2/metrics/cluster

# Health check
curl http://localhost:9000/minio/health/live
```

## Troubleshooting

### Connection Issues
```bash
# Check MinIO is running
docker compose ps minio

# Check MinIO logs
docker compose logs minio

# Test connection
docker compose exec backend python3 -c "
from src.minio_client import get_minio_client
client = get_minio_client()
print('Buckets:', list(client.client.list_buckets()))
"
```

### Permission Issues
```bash
# Check bucket policy
mc admin policy list myminio

# Grant access
mc admin policy set myminio readwrite user=backend
```

### Performance Issues
```bash
# Check disk I/O
iostat -x 1

# Check MinIO metrics
mc admin info myminio

# Increase connection pool
# In minio_client.py, configure:
# client = Minio(..., http_client=...)
```

## Rollback Plan

If you need to rollback to filesystem storage:

1. Stop application
2. Restore old code from git: `git checkout <previous-commit>`
3. Restore filesystem backup: `tar -xzf storage_backup.tar.gz`
4. Remove MinIO from docker-compose.yaml
5. Restart application

## Resources

- [MinIO Documentation](https://min.io/docs/)
- [MinIO Python Client](https://min.io/docs/minio/linux/developers/python/minio-py.html)
- [S3 API Reference](https://docs.aws.amazon.com/AmazonS3/latest/API/)
- [MinIO Security Best Practices](https://min.io/docs/minio/linux/operations/security.html)

## Summary

✅ **Storage**: Filesystem → MinIO (S3-compatible)  
✅ **Scalability**: Single server → Horizontally scalable  
✅ **API**: Fully backward compatible  
✅ **Security**: Built-in access control + encryption  
✅ **Cloud-Ready**: Production-ready architecture  
