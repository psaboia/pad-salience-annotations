-- Migration: Multi-role users
-- Allow users to have multiple roles (admin and/or specialist)

-- Create user_roles table
CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'specialist')),
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, role)
);

-- Migrate existing roles from users table to user_roles table
INSERT INTO user_roles (user_id, role)
SELECT id, role FROM users WHERE role IS NOT NULL;

-- Note: We keep the 'role' column in users table for now as a "default" or "primary" role
-- This maintains backward compatibility and simplifies queries

-- Record migration
INSERT OR IGNORE INTO migrations (version) VALUES ('006_multi_role_users');
