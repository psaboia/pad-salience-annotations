-- PAD Salience Annotation System - Specialist Profile Fields
-- Version: 003
-- Created: 2025-01-17

-- Add profile fields for specialists
ALTER TABLE users ADD COLUMN years_experience INTEGER;
ALTER TABLE users ADD COLUMN training_date TEXT;
ALTER TABLE users ADD COLUMN institution TEXT;
ALTER TABLE users ADD COLUMN specializations TEXT;  -- JSON array

-- Insert migration record
INSERT OR IGNORE INTO migrations (version) VALUES ('003_specialist_profile');
