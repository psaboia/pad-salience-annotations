-- Audio transcription tables (Whisper API)
CREATE TABLE IF NOT EXISTS transcriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    language TEXT,
    duration_seconds REAL,
    full_text TEXT,
    transcription_response_json TEXT,
    transcription_error TEXT,
    model TEXT DEFAULT 'whisper-1',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    FOREIGN KEY (session_id) REFERENCES annotation_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transcription_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcription_id INTEGER NOT NULL,
    word_index INTEGER NOT NULL,
    word TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    FOREIGN KEY (transcription_id) REFERENCES transcriptions(id) ON DELETE CASCADE
);
