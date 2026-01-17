-- PAD Salience Annotation System - Initial Schema
-- Version: 001
-- Created: 2025-01-17

-- Users table (admin and specialists)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'specialist')),
    expertise_level TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Samples table (imported from manifest.json)
CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name TEXT NOT NULL,
    drug_name_display TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    image_path TEXT NOT NULL,
    quantity INTEGER,
    image_type TEXT DEFAULT 'processed',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_samples_drug_name ON samples(drug_name);
CREATE INDEX IF NOT EXISTS idx_samples_card_id ON samples(card_id);

-- Experiments table
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    instructions TEXT,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'paused', 'completed', 'archived')),
    created_by INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);

-- Experiment samples (base order for an experiment)
CREATE TABLE IF NOT EXISTS experiment_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,
    sample_id INTEGER NOT NULL,
    display_order INTEGER NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_id) REFERENCES samples(id),
    UNIQUE(experiment_id, sample_id),
    UNIQUE(experiment_id, display_order)
);

CREATE INDEX IF NOT EXISTS idx_experiment_samples_experiment ON experiment_samples(experiment_id);

-- Specialist assignments to experiments
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,
    specialist_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'paused')),
    randomization_seed INTEGER,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (specialist_id) REFERENCES users(id),
    UNIQUE(experiment_id, specialist_id)
);

CREATE INDEX IF NOT EXISTS idx_assignments_specialist ON assignments(specialist_id);
CREATE INDEX IF NOT EXISTS idx_assignments_experiment ON assignments(experiment_id);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status);

-- Randomized sample order per specialist assignment
CREATE TABLE IF NOT EXISTS specialist_sample_order (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    experiment_sample_id INTEGER NOT NULL,
    specialist_order INTEGER NOT NULL,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (experiment_sample_id) REFERENCES experiment_samples(id) ON DELETE CASCADE,
    UNIQUE(assignment_id, experiment_sample_id),
    UNIQUE(assignment_id, specialist_order)
);

CREATE INDEX IF NOT EXISTS idx_specialist_order_assignment ON specialist_sample_order(assignment_id);

-- Annotation sessions (ONE per sample per specialist - enforced by UNIQUE constraint)
CREATE TABLE IF NOT EXISTS annotation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    experiment_sample_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    session_uuid TEXT UNIQUE NOT NULL,
    audio_filename TEXT,
    audio_duration_ms INTEGER,
    image_dimensions_json TEXT,
    layout_settings_json TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (experiment_sample_id) REFERENCES experiment_samples(id),
    UNIQUE(assignment_id, experiment_sample_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_assignment ON annotation_sessions(assignment_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON annotation_sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_uuid ON annotation_sessions(session_uuid);

-- Individual annotations within a session
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    annotation_type TEXT NOT NULL CHECK (annotation_type IN ('rectangle', 'polygon')),
    color TEXT,
    lanes_json TEXT,  -- JSON array of lane letters e.g. ["D", "E", "F"]
    bbox_normalized_json TEXT,  -- JSON: {x1, y1, x2, y2} normalized 0-999
    points_normalized_json TEXT,  -- JSON array for polygons: [{x, y}, ...]
    timestamp_start_ms INTEGER,
    timestamp_end_ms INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES annotation_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_annotations_session ON annotations(session_id);

-- Legacy annotations (migrated from annotations.jsonl)
CREATE TABLE IF NOT EXISTS legacy_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_session_id TEXT NOT NULL,
    original_timestamp TEXT,
    sample_json TEXT NOT NULL,
    image_dimensions_json TEXT,
    annotations_json TEXT,
    audio_filename TEXT,
    audio_duration_ms INTEGER,
    specialist_id TEXT,
    specialist_expertise TEXT,
    layout_settings_json TEXT,
    migrated_at TEXT DEFAULT (datetime('now'))
);

-- Migration tracking
CREATE TABLE IF NOT EXISTS migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    applied_at TEXT DEFAULT (datetime('now'))
);

-- Insert initial migration record
INSERT OR IGNORE INTO migrations (version) VALUES ('001_initial_schema');
