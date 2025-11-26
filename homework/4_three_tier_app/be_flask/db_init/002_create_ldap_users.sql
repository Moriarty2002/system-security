-- Create new LDAP users table
-- This table stores only application-specific user metadata
-- Passwords and roles are managed by LDAP, not stored here
-- Roles are determined by LDAP group membership

CREATE TABLE IF NOT EXISTS ldap_users (
    username TEXT PRIMARY KEY,
    quota BIGINT NOT NULL DEFAULT 0,
    last_login TIMESTAMP
);

-- Create index for performance on last_login lookups
CREATE INDEX IF NOT EXISTS idx_ldap_users_last_login ON ldap_users(last_login);

-- Migrate existing users to ldap_users table (preserving quota)
-- This is a one-time migration
INSERT INTO ldap_users (username, quota)
SELECT username, quota
FROM users
WHERE NOT EXISTS (SELECT 1 FROM ldap_users WHERE ldap_users.username = users.username);

-- Create bin_items table if it doesn't exist
-- Update foreign key to reference ldap_users instead of users
CREATE TABLE IF NOT EXISTS bin_items (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL REFERENCES ldap_users(username) ON DELETE CASCADE,
    original_path TEXT NOT NULL,
    item_type VARCHAR(32) NOT NULL,
    size BIGINT NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bin_path TEXT NOT NULL
);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_bin_items_username ON bin_items(username);
CREATE INDEX IF NOT EXISTS idx_bin_items_deleted_at ON bin_items(deleted_at);
