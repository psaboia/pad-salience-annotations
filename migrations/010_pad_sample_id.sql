-- Add pad_sample_id to samples table to store the original sample_id from PAD Analytics
ALTER TABLE samples ADD COLUMN pad_sample_id INTEGER;

INSERT OR IGNORE INTO migrations (version) VALUES ('010_pad_sample_id');
