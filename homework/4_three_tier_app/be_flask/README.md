# Flask Backend Application

A modular Flask application for file storage and user management with role-based access control.

## Architecture

The application has been refactored into a modular structure for better maintainability and code quality:

```
be_flask/
├── be.py                 # Main application entry point
├── __init__.py          # Application factory
├── models.py            # Database models
├── config.py            # Configuration management
├── vault_client.py      # Vault client for secrets management
├── s3_client.py         # AWS S3 client with Roles Anywhere authentication
├── auth.py              # Authentication and authorization logic
├── utils_s3.py       # Utility functions for S3 operations
├── blueprints/          # Route blueprints
│   ├── auth.py          # Authentication endpoints
│   ├── files.py         # File management endpoints
│   └── admin.py         # Administrative endpoints
├── db_init/             # Database initialization scripts
├── requirements.txt     # Python dependencies
└── Dockerfile          # Docker configuration
```

## Features

- **User Authentication**: Authentication is delegated to Keycloak (OpenID Connect). The backend validates Keycloak-issued JWTs and implements role-based access control based on token claims.
- **File Storage**: Files stored in AWS S3 using IAM Roles Anywhere authentication with X.509 certificates
- **Secrets Management**: All secrets (database credentials, S3 certificates, Keycloak config) managed by HashiCorp Vault
- **File Management**: Upload, download, delete files with quota enforcement
- **User Management**: Admin interface for user creation and quota management
- **Role-based Access**: Support for user, moderator, and admin roles
- **Database Integration**: SQLAlchemy with PostgreSQL
- **Logging**: Comprehensive logging for debugging and monitoring
- **Error Handling**: Proper error responses and logging

## API Endpoints

### Authentication
- `GET /auth/whoami` - Get current user info (frontend obtains tokens via Keycloak-hosted login; the backend validates these tokens)

Notes:
- The application does not handle user credential submission. Users authenticate via the Keycloak-hosted login page (OIDC). The backend exposes `/auth/config` to let the frontend discover Keycloak server URL, realm, and client id.

### File Operations
- `POST /files/upload` - Upload a file
- `GET /files/` - List user's files
- `GET /files/<filename>` - Download a file
- `DELETE /files/<filename>` - Delete a file
- `GET /files/users` - List usernames (moderator/admin only)

### Administration
- `GET /admin/users` - List all users (admin only)
- `POST /admin/users` - Create new user (admin only)
- `PUT /admin/users/<username>/quota` - Update user quota (admin only)

## Configuration

The application requires configuration through HashiCorp Vault. All secrets are stored in Vault:

### Vault Secrets Required

**Path: `mes_local_cloud/app/flask`**
- `jwt_secret`: JWT signing key
- `admin_password`, `alice_password`, `moderator_password`: User passwords
- `flask_aws_s3_certificate`: X.509 certificate for AWS Roles Anywhere (PEM format)
- `flask_aws_s3_key`: Private key for AWS Roles Anywhere (PEM format)
- `aws_region`: AWS region (e.g., us-east-1)
- `aws_s3_bucket`: S3 bucket name
- `aws_trust_anchor_arn`: ARN of AWS Roles Anywhere trust anchor
- `aws_profile_arn`: ARN of AWS Roles Anywhere profile
- `aws_role_arn`: ARN of IAM role to assume

**Path: `mes_local_cloud/database/postgres`**
- `username`, `password`, `database`, `host`, `port`: PostgreSQL connection parameters

**Path: `keycloak/client`**
- `server_url`, `server_url_external`, `realm`, `client_id`, `client_secret`: Keycloak configuration

### Environment Variables
- `VAULT_ADDR`: Vault server address
- `VAULT_ROLE_ID`: Vault AppRole role ID
- `VAULT_SECRET_ID`: Vault AppRole secret ID
- `FLASK_ENV`: Environment (development/production)

## Running the Application

### Local Development
```bash
cd be_flask
pip install -r requirements.txt
python be.py
```

### Docker
```bash
docker build -t flask-backend .
docker run -p 5000:5000 flask-backend
```

### Docker Compose
The application is part of a larger Docker Compose setup in the parent directory.

## Security Features

- **AWS Roles Anywhere Authentication**: X.509 certificate-based authentication for S3 access (no long-term credentials)
- **HashiCorp Vault Integration**: All secrets managed securely in Vault
- JWT token authentication via Keycloak
- Secure filename handling
- Path traversal protection
- Role-based access control
- Quota enforcement
- Database transaction locking for concurrent operations

## Code Quality Improvements

- **Modular Structure**: Separated concerns into logical modules
- **Type Hints**: Added type annotations for better code documentation
- **Error Handling**: Comprehensive error handling with proper logging
- **Logging**: Structured logging for debugging and monitoring
- **Configuration Management**: Centralized configuration with environment support
- **Blueprint Organization**: Routes organized into logical blueprints