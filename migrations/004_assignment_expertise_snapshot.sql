-- PAD Salience Annotation System - Assignment Expertise Snapshot
-- Version: 004
-- Created: 2025-01-17
-- Purpose: Capture specialist profile at assignment time for historical accuracy

-- Capturar perfil do especialista no momento do assignment
ALTER TABLE assignments ADD COLUMN expertise_level_snapshot TEXT;
ALTER TABLE assignments ADD COLUMN years_experience_snapshot INTEGER;
ALTER TABLE assignments ADD COLUMN training_date_snapshot TEXT;

-- Insert migration record
INSERT OR IGNORE INTO migrations (version) VALUES ('004_assignment_expertise_snapshot');
