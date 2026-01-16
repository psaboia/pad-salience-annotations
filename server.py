"""
PAD Salience Annotation Server

Simple FastAPI server that:
1. Serves the annotation prototype
2. Saves annotations to data/annotations.jsonl
3. Saves audio files to data/audio/
"""

import json
import base64
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Any

app = FastAPI(title="PAD Salience Annotation Server")

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
ANNOTATIONS_FILE = DATA_DIR / "annotations.jsonl"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)


class AudioData(BaseModel):
    format: str
    data_base64: str
    duration_ms: Optional[int] = None


class AnnotationSession(BaseModel):
    session_id: str
    timestamp: str
    sample: dict
    image_dimensions: dict
    annotations: list
    audio: Optional[AudioData] = None
    specialist_id: Optional[str] = None
    specialist_expertise: Optional[str] = None


@app.post("/api/save-annotation")
async def save_annotation(session: AnnotationSession):
    """Save annotation session to JSONL and audio to separate file."""

    try:
        # Prepare data for JSONL (without base64 audio data)
        session_data = session.model_dump()
        audio_filename = None

        # Save audio file separately if present
        if session.audio and session.audio.data_base64:
            audio_filename = f"{session.session_id}.webm"
            audio_path = AUDIO_DIR / audio_filename

            # Decode and save audio
            audio_bytes = base64.b64decode(session.audio.data_base64)
            audio_path.write_bytes(audio_bytes)

            # Replace audio data with filename reference
            session_data["audio"] = {
                "format": session.audio.format,
                "filename": audio_filename,
                "duration_ms": session.audio.duration_ms
            }

        # Append to JSONL
        with open(ANNOTATIONS_FILE, "a") as f:
            f.write(json.dumps(session_data) + "\n")

        # Count total annotations
        total_sessions = sum(1 for _ in open(ANNOTATIONS_FILE)) if ANNOTATIONS_FILE.exists() else 1

        return {
            "status": "success",
            "session_id": session.session_id,
            "audio_saved": audio_filename is not None,
            "total_sessions": total_sessions
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get annotation statistics."""

    stats = {
        "total_sessions": 0,
        "total_annotations": 0,
        "drugs_annotated": set(),
        "audio_files": 0
    }

    if ANNOTATIONS_FILE.exists():
        with open(ANNOTATIONS_FILE) as f:
            for line in f:
                if line.strip():
                    session = json.loads(line)
                    stats["total_sessions"] += 1
                    stats["total_annotations"] += len(session.get("annotations", []))
                    if "sample" in session:
                        stats["drugs_annotated"].add(session["sample"].get("drug_name", "unknown"))

    stats["drugs_annotated"] = list(stats["drugs_annotated"])
    stats["audio_files"] = len(list(AUDIO_DIR.glob("*.webm")))

    return stats


# Serve static files
app.mount("/sample_images", StaticFiles(directory=BASE_DIR / "sample_images"), name="sample_images")
app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")
app.mount("/prototype", StaticFiles(directory=BASE_DIR / "prototype", html=True), name="prototype")


@app.get("/")
async def root():
    """Redirect to prototype."""
    return FileResponse(BASE_DIR / "prototype" / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
