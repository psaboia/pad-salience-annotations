-- PAD Salience Annotation System - Sample Tags for AprilTag Identification
-- Version: 002
-- Created: 2025-01-17
--
-- This migration adds support for unique AprilTag combinations per sample,
-- enabling automatic image identification via eye-tracking systems.
-- See docs/apriltag-identification-system.md for design decisions.

-- Tags associated with each sample for eye-tracking identification
CREATE TABLE IF NOT EXISTS sample_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL CHECK (tag_id >= 0 AND tag_id <= 586),  -- AprilTag tag36h11 range
    position TEXT NOT NULL CHECK (position IN ('top-left', 'top-right', 'bottom-left', 'bottom-right')),
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE,
    UNIQUE(sample_id, position),  -- One tag per position per sample
    UNIQUE(sample_id, tag_id)     -- Each tag used only once per sample
);

CREATE INDEX IF NOT EXISTS idx_sample_tags_sample ON sample_tags(sample_id);
CREATE INDEX IF NOT EXISTS idx_sample_tags_tag ON sample_tags(tag_id);

-- Insert migration record
INSERT OR IGNORE INTO migrations (version) VALUES ('002_sample_tags');
