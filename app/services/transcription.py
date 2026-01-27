"""Audio transcription service using OpenAI Whisper API."""

import json
import os
from pathlib import Path

import httpx

from ..database import get_db_context, json_dumps

BASE_DIR = Path(__file__).parent.parent.parent
AUDIO_DIR = BASE_DIR / "data" / "audio"
ENV_FILE = BASE_DIR / ".env"

OPENAI_API_URL = "https://api.openai.com/v1/audio/transcriptions"
WHISPER_MODEL = "whisper-1"
TRANSCRIPTION_TIMEOUT = 120.0  # seconds


def _get_openai_api_key() -> str | None:
    """Get OPENAI_API_KEY from environment or .env file."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    # Fallback: read from .env file
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip()
    return None


def is_transcription_available() -> bool:
    """Check if transcription is available (API key configured)."""
    return bool(_get_openai_api_key())


async def transcribe_session(session_id: int) -> None:
    """Transcribe audio for a session using OpenAI Whisper API.

    This function is designed to be called as a background task.
    It manages its own database connections and error handling.
    """
    api_key = _get_openai_api_key()
    if not api_key:
        return

    async with get_db_context() as db:
        # Get session info
        cursor = await db.execute(
            "SELECT audio_filename FROM annotation_sessions WHERE id = ?",
            (session_id,)
        )
        row = await cursor.fetchone()
        if not row or not row["audio_filename"]:
            return

        audio_filename = row["audio_filename"]
        audio_path = AUDIO_DIR / audio_filename

        if not audio_path.exists():
            # Create failed transcription record
            await db.execute(
                """
                INSERT OR REPLACE INTO transcriptions (session_id, status, transcription_error, model)
                VALUES (?, 'failed', ?, ?)
                """,
                (session_id, f"Audio file not found: {audio_filename}", WHISPER_MODEL)
            )
            await db.commit()
            return

        # Check if already transcribed successfully
        cursor = await db.execute(
            "SELECT id, status FROM transcriptions WHERE session_id = ?",
            (session_id,)
        )
        existing = await cursor.fetchone()
        if existing and existing["status"] == "completed":
            return

        # Create or update transcription record as in_progress
        if existing:
            await db.execute(
                """
                UPDATE transcriptions
                SET status = 'in_progress', transcription_error = NULL, completed_at = NULL
                WHERE session_id = ?
                """,
                (session_id,)
            )
        else:
            await db.execute(
                """
                INSERT INTO transcriptions (session_id, status, model)
                VALUES (?, 'in_progress', ?)
                """,
                (session_id, WHISPER_MODEL)
            )
        await db.commit()

        # Get the transcription_id
        cursor = await db.execute(
            "SELECT id FROM transcriptions WHERE session_id = ?",
            (session_id,)
        )
        transcription = await cursor.fetchone()
        transcription_id = transcription["id"]

    # Call Whisper API outside the DB context to avoid holding the connection
    try:
        async with httpx.AsyncClient(timeout=TRANSCRIPTION_TIMEOUT) as client:
            with open(audio_path, "rb") as audio_file:
                response = await client.post(
                    OPENAI_API_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (audio_filename, audio_file, "audio/webm")},
                    data={
                        "model": WHISPER_MODEL,
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "word",
                    },
                )

        if response.status_code != 200:
            error_msg = f"Whisper API error {response.status_code}: {response.text[:500]}"
            async with get_db_context() as db:
                await db.execute(
                    """
                    UPDATE transcriptions
                    SET status = 'failed', transcription_error = ?
                    WHERE id = ?
                    """,
                    (error_msg, transcription_id)
                )
                await db.commit()
            return

        result = response.json()

    except httpx.TimeoutException:
        async with get_db_context() as db:
            await db.execute(
                """
                UPDATE transcriptions
                SET status = 'failed', transcription_error = 'Whisper API timeout'
                WHERE id = ?
                """,
                (transcription_id,)
            )
            await db.commit()
        return
    except Exception as e:
        async with get_db_context() as db:
            await db.execute(
                """
                UPDATE transcriptions
                SET status = 'failed', transcription_error = ?
                WHERE id = ?
                """,
                (str(e)[:500], transcription_id)
            )
            await db.commit()
        return

    # Save results
    async with get_db_context() as db:
        full_text = result.get("text", "")
        language = result.get("language", "")
        duration = result.get("duration")

        await db.execute(
            """
            UPDATE transcriptions
            SET status = 'completed',
                language = ?,
                duration_seconds = ?,
                full_text = ?,
                transcription_response_json = ?,
                transcription_error = NULL,
                completed_at = datetime('now')
            WHERE id = ?
            """,
            (language, duration, full_text, json.dumps(result), transcription_id)
        )

        # Clear old words if re-transcribing
        await db.execute(
            "DELETE FROM transcription_words WHERE transcription_id = ?",
            (transcription_id,)
        )

        # Save individual words with timestamps
        words = result.get("words", [])
        for idx, word_data in enumerate(words):
            start_ms = int(word_data["start"] * 1000)
            end_ms = int(word_data["end"] * 1000)
            await db.execute(
                """
                INSERT INTO transcription_words (transcription_id, word_index, word, start_ms, end_ms)
                VALUES (?, ?, ?, ?, ?)
                """,
                (transcription_id, idx, word_data["word"], start_ms, end_ms)
            )

        await db.commit()


async def get_transcription_for_session(session_id: int) -> dict | None:
    """Get transcription data for a session, including words."""
    async with get_db_context() as db:
        cursor = await db.execute(
            """
            SELECT id, session_id, status, language, duration_seconds,
                   full_text, transcription_error, model, created_at, completed_at
            FROM transcriptions
            WHERE session_id = ?
            """,
            (session_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        transcription = dict(row)

        # Get words if completed
        if transcription["status"] == "completed":
            cursor = await db.execute(
                """
                SELECT word_index, word, start_ms, end_ms
                FROM transcription_words
                WHERE transcription_id = ?
                ORDER BY word_index
                """,
                (transcription["id"],)
            )
            words = [dict(w) for w in await cursor.fetchall()]
            transcription["words"] = words
        else:
            transcription["words"] = []

        return transcription
