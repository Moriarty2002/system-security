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

- **User Authentication**: Authentication is delegated to Keycloak (OpenID Connect). The backend validates Keycloak-issued JWTs and implements role-based access control based on token claims.
- **File Management**: Upload, download, delete files with quota enforcement
- **User Management**: Admin interface for user creation and quota management
- **Role-based Access**: Support for user, moderator, and admin roles
- **Database Integration**: SQLAlchemy with support for SQLite and PostgreSQL
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

The application supports multiple configuration environments:

- **Development**: Debug mode enabled, SQLite database
- **Production**: Debug mode disabled, configurable database

Set environment variables:
- `SECRET_KEY`: JWT signing key
- `DATABASE_URL`: Database connection string
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