-- Add eyetracking_mode to studies table
-- Values: 'disabled' (default), 'required'
ALTER TABLE studies ADD COLUMN eyetracking_mode TEXT DEFAULT 'disabled';
