-- Add default image dimensions to studies for metadata export fallback
ALTER TABLE studies ADD COLUMN default_image_width INTEGER;
ALTER TABLE studies ADD COLUMN default_image_height INTEGER;

INSERT OR IGNORE INTO migrations (version) VALUES ('011_study_image_dimensions');
