-- Migration: Add annotation_mode to studies
-- Version: 009
--
-- Adds annotation_mode field to control how specialists annotate:
-- - 'drawing': Traditional mode with rectangles/polygons (default)
-- - 'audio_only': Only audio recording + eye-tracking, no drawing tools

ALTER TABLE studies ADD COLUMN annotation_mode TEXT DEFAULT 'drawing'
    CHECK (annotation_mode IN ('drawing', 'audio_only'));

-- Insert migration record
INSERT OR IGNORE INTO migrations (version) VALUES ('009_annotation_mode');
