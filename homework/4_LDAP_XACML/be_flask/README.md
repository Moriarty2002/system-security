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
├── auth.py              # Authentication and authorization logic
├── utils.py             # Utility functions for file operations
├── blueprints/          # Route blueprints
│   ├── auth.py          # Authentication endpoints
│   ├── files.py         # File management endpoints
│   └── admin.py         # Administrative endpoints
├── db_init/             # Database initialization scripts
├── storage/             # User file storage directory
├── requirements.txt     # Python dependencies
└── Dockerfile          # Docker configuration
```

## Features

- **User Authentication**: JWT-based authentication with role-based access control
- **File Management**: Upload, download, delete files with quota enforcement
- **User Management**: Admin interface for user creation and quota management
- **Role-based Access**: Support for user, moderator, and admin roles
- **Database Integration**: SQLAlchemy with support for SQLite and PostgreSQL
- **Logging**: Comprehensive logging for debugging and monitoring
- **Error Handling**: Proper error responses and logging

## API Endpoints

### Authentication
- `POST /auth/login` - User login
- `GET /auth/whoami` - Get current user info

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

The application supports multiple configuration environments:

- **Development**: Debug mode enabled, SQLite database
- **Production**: Debug mode disabled, configurable database

Set environment variables:
- `SECRET_KEY`: JWT signing key
- `DATABASE_URL`: Database connection string
- `FLASK_ENV`: Environment (development/production)

### Optional: HashiCorp Vault integration

- To improve secret handling, the app can load secrets from HashiCorp Vault (KV v2) at the path `secret/flask`.
- The app will attempt to load secrets when `VAULT_ADDR` is set and the `hvac` Python package is installed.
- Authentication methods supported:
	- Token auth: set `VAULT_TOKEN`
	- AppRole: set `VAULT_ROLE_ID` and `VAULT_SECRET_ID`
- Secrets written to Vault should be keys such as `SECRET_KEY` and `DATABASE_URL` (other keys are supported).

Run Vault locally via `docker-compose` (development/dev mode): the top-level `docker-compose.yaml` contains an optional `vault` service and a `vault-init` one-shot initializer that will populate `secret/flask` for demo purposes.

Alternatively, run Vault separately (recommended for production) and ensure the Flask container has connectivity and appropriate credentials.

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

- JWT token authentication
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