-- Minimal user_profiles table for Keycloak-based authentication
-- Only stores application-specific data not managed by Keycloak
--
-- Keycloak manages: authentication, credentials, user basic info, timestamps
-- Application manages: quota (storage limits)

CREATE TABLE IF NOT EXISTS user_profiles (
    keycloak_id UUID PRIMARY KEY,          -- Links to Keycloak user ID
    username VARCHAR(128) UNIQUE NOT NULL, -- Cached from Keycloak for lookups
    quota BIGINT NOT NULL DEFAULT 0        -- Application-specific: storage quota in bytes
);

-- Index for faster username lookups (used by file operations)
CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles(username);

-- Note: Role is intentionally NOT stored here
-- It's fetched from Keycloak token on each request for security
-- This ensures role changes in Keycloak take effect immediately

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

CREATE INDEX IF NOT EXISTS idx_bin_items_username ON bin_items(username);
