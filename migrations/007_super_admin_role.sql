-- Migration: Add super_admin role
-- Super admin can manage users, regular admin can only manage studies
-- Note: user_roles table already supports super_admin from schema
-- Note: users.role field is legacy, we use user_roles as source of truth

-- Promote existing admins to super_admin in user_roles table
UPDATE user_roles SET role = 'super_admin' WHERE role = 'admin';

-- Record migration
INSERT OR IGNORE INTO migrations (version) VALUES ('007_super_admin_role');
