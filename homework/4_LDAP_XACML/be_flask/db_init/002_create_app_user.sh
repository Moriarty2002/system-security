#!/bin/bash
set -e

# This script runs after PostgreSQL initialization
# Creates an application user with limited privileges

echo "Creating application user for Flask backend..."

# Get credentials from environment
ADMIN_USER="${POSTGRES_USER:-admin}"
APP_USER="${POSTGRES_APP_USER:-flask_app}"
APP_PASSWORD="${POSTGRES_APP_PASSWORD:-flask_app_password}"
DB_NAME="${POSTGRES_DB:-postgres_db}"

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
