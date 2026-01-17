-- PAD Salience Annotation System - Rename Experiment to Study
-- Version: 005
-- Created: 2025-01-17
-- Purpose: Rename "experiment" terminology to "study" throughout the database

-- Rename main tables
ALTER TABLE experiments RENAME TO studies;
ALTER TABLE experiment_samples RENAME TO study_samples;

-- Rename columns in study_samples (formerly experiment_samples)
ALTER TABLE study_samples RENAME COLUMN experiment_id TO study_id;

-- Rename columns in assignments
ALTER TABLE assignments RENAME COLUMN experiment_id TO study_id;

-- Rename columns in specialist_sample_order
ALTER TABLE specialist_sample_order RENAME COLUMN experiment_sample_id TO study_sample_id;

-- Rename columns in annotation_sessions
ALTER TABLE annotation_sessions RENAME COLUMN experiment_sample_id TO study_sample_id;

-- Drop old indexes and create new ones with updated names
DROP INDEX IF EXISTS idx_experiments_status;
CREATE INDEX IF NOT EXISTS idx_studies_status ON studies(status);

DROP INDEX IF EXISTS idx_experiment_samples_experiment;
CREATE INDEX IF NOT EXISTS idx_study_samples_study ON study_samples(study_id);

DROP INDEX IF EXISTS idx_assignments_experiment;
CREATE INDEX IF NOT EXISTS idx_assignments_study ON assignments(study_id);

-- Insert migration record
INSERT OR IGNORE INTO migrations (version) VALUES ('005_rename_experiment_to_study');
