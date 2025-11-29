-- Minimal user_profiles table for Keycloak-based authentication
-- Only stores application-specific data not managed by Keycloak
--
-- KEYCLOAK MANAGES: authentication, credentials, username, user info, creation/update timestamps
-- APPLICATION MANAGES: quota (storage limits)
--
-- NOTE: The original 'users' table with password_hash remains unchanged
--       but is no longer used by the application
-- NOTE: Username is NOT cached - always fetched from validated Keycloak token
--       This prevents sync issues if username changes in Keycloak

CREATE TABLE IF NOT EXISTS user_profiles (
    keycloak_id UUID PRIMARY KEY,          -- Links to Keycloak user ID (sub claim)
    quota BIGINT NOT NULL DEFAULT 104857600 -- Storage quota in bytes (100MB default)
);

-- IMPORTANT: Role and username are NOT stored in this table
-- Reason: Both are fetched from Keycloak token on each request
-- This ensures always-fresh values and automatic sync with Keycloak changes
-- Benefit: Role changes in Keycloak take effect immediately, no sync needed

-- Keep bin_items table structure (uses username for lookups)
CREATE TABLE IF NOT EXISTS bin_items (
    id SERIAL PRIMARY KEY,
    username VARCHAR(128) NOT NULL,
    original_path VARCHAR(1024) NOT NULL,
    item_type VARCHAR(32) NOT NULL,
    size BIGINT NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bin_path VARCHAR(1024) NOT NULL
);

-- Index for bin_items username lookups
CREATE INDEX IF NOT EXISTS idx_bin_items_username ON bin_items(username);
