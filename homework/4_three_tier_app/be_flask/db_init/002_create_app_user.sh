#!/bin/bash
set -e

# This script runs after PostgreSQL initialization
# Creates an application user with limited privileges
#
# SECURITY ARCHITECTURE:
# - This script creates 'flask_app' user during DB initialization
# - Password is passed via POSTGRES_APP_PASSWORD environment variable
# - Same password is stored in Vault at: secret/mes_local_cloud/database/postgres
# - Flask application retrieves credentials from Vault (NOT from .env)
# - This ensures Flask connects with least-privilege user

echo "Creating application user for Flask backend..."

# Get credentials from environment (fail fast if not provided)
if [ -z "$POSTGRES_USER" ]; then
    echo "ERROR: POSTGRES_USER environment variable is required"
    exit 1
fi
if [ -z "$POSTGRES_APP_USER" ]; then
    echo "ERROR: POSTGRES_APP_USER environment variable is required"
    exit 1
fi
if [ -z "$POSTGRES_APP_PASSWORD" ]; then
    echo "ERROR: POSTGRES_APP_PASSWORD environment variable is required"
    exit 1
fi
if [ -z "$POSTGRES_DB" ]; then
    echo "ERROR: POSTGRES_DB environment variable is required"
    exit 1
fi

ADMIN_USER="$POSTGRES_USER"
APP_USER="$POSTGRES_APP_USER"
APP_PASSWORD="$POSTGRES_APP_PASSWORD"
DB_NAME="$POSTGRES_DB"

# Create application user
psql -v ON_ERROR_STOP=1 --username "$ADMIN_USER" --dbname "$DB_NAME" <<-EOSQL
    -- Create application user if not exists
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$APP_USER') THEN
            CREATE USER $APP_USER WITH PASSWORD '$APP_PASSWORD';
        END IF;
    END
    \$\$;

    -- Grant connect privilege to the database
    GRANT CONNECT ON DATABASE $DB_NAME TO $APP_USER;

    -- Grant usage on public schema
    GRANT USAGE ON SCHEMA public TO $APP_USER;

    -- Grant privileges on existing tables
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $APP_USER;

    -- Grant privileges on sequences (for auto-increment columns)
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO $APP_USER;

    -- Change owner of existing tables to app user (so it can ALTER them)
    DO \$\$
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        LOOP
            EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO $APP_USER';
        END LOOP;
    END
    \$\$;

    -- Change owner of sequences
    DO \$\$
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'
        LOOP
            EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequencename) || ' OWNER TO $APP_USER';
        END LOOP;
    END
    \$\$;

    -- Make sure future tables also get these privileges
    ALTER DEFAULT PRIVILEGES IN SCHEMA public 
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $APP_USER;

    ALTER DEFAULT PRIVILEGES IN SCHEMA public 
        GRANT USAGE, SELECT ON SEQUENCES TO $APP_USER;

    -- Revoke schema creation privilege (security)
    REVOKE CREATE ON SCHEMA public FROM $APP_USER;
EOSQL

echo "Application user '$APP_USER' created successfully with limited privileges"
