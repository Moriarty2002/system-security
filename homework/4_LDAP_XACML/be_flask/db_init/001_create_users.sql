-- Create users table and seed initial users (admin, alice, moderator)
-- This script is executed by the official Postgres image when the DB directory is empty.

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    quota BIGINT NOT NULL DEFAULT 0,
    password_hash VARCHAR(512) NOT NULL
);

-- Insert seed users if they don't exist already
INSERT INTO users (username, is_admin, role, quota, password_hash)
SELECT 'admin', true, 'admin', 10737418240, 'scrypt:32768:8:1$HabprHb5EaJ4bzpQ$3d609768ce85ab0dc95065264be6b8f4657862f6702b91011e7e82149fbd59380a99ac900856feea4c5dde68b3e57247d18c8de95f1f457af4d0fc6f9af69ef4'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');

INSERT INTO users (username, is_admin, role, quota, password_hash)
SELECT 'alice', false, 'user', 104857600, 'scrypt:32768:8:1$DnDI8Hv5vbGMJ3PI$b9d04d717ed43bdbb3078aeb7af5df509c2fb0a010cd499078651f4ded9d620bda76052f2f93d2db45fd407e8667b0184e4752be3864069fef602de087af13ad'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'alice');

INSERT INTO users (username, is_admin, role, quota, password_hash)
SELECT 'moderator', false, 'moderator', 524288000, 'scrypt:32768:8:1$qLCBfiKWrJgFDG6v$ecdab5441076e61b8aa8cc5ac72c84539e5dbead646c9f35acfe4e9e61a3c1bd9fc2bed8fde709ee1906e265778ae73e4b957b99c5ea8edbb5cfe8fb7af67d35'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'moderator');
