"""
PAD Salience Annotation Server - Main Application

This is the main entry point for the FastAPI application with experiment management.
"""

import json
import base64
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Any

from .database import init_db, get_db_context, import_samples_from_manifest, migrate_legacy_annotations
from .routers import auth_router, admin_router, specialist_router
from .services.auth import get_current_user_optional

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
ANNOTATIONS_FILE = DATA_DIR / "annotations.jsonl"
CONFIG_FILE = BASE_DIR / "config.yaml"
MANIFEST_FILE = BASE_DIR / "sample_images" / "manifest.json"
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)


def load_config():
    """Load configuration from YAML file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - run on startup and shutdown."""
    # Startup
    print("Initializing database...")
    await init_db()

    # Import samples from manifest if not already in DB
    async with get_db_context() as db:
        cursor = await db.execute("SELECT COUNT(*) as count FROM samples")
        row = await cursor.fetchone()
        if row["count"] == 0 and MANIFEST_FILE.exists():
            print("Importing samples from manifest.json...")
            await import_samples_from_manifest(db, MANIFEST_FILE)
            print("Samples imported successfully")

        # Migrate legacy annotations if present
        cursor = await db.execute("SELECT COUNT(*) as count FROM legacy_annotations")
        row = await cursor.fetchone()
        if row["count"] == 0 and ANNOTATIONS_FILE.exists():
            print("Migrating legacy annotations...")
            count = await migrate_legacy_annotations(db, ANNOTATIONS_FILE)
            print(f"Migrated {count} legacy annotation sessions")

    print("Server ready!")

    yield

    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="PAD Salience Annotation Server",
    description="Experiment management system for PAD image annotations",
    version="2.0.0",
    lifespan=lifespan
)

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Include routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(specialist_router)


# Legacy API support for backward compatibility
class AudioData(BaseModel):
    format: str
    data_base64: str
    duration_ms: Optional[int] = None


class LegacyAnnotationSession(BaseModel):
    session_id: str
    timestamp: str
    sample: dict
    image_dimensions: dict
    annotations: list
    audio: Optional[AudioData] = None
    specialist_id: Optional[str] = None
    specialist_expertise: Optional[str] = None
    layout_settings: Optional[dict] = None


@app.post("/api/save-annotation")
async def save_annotation(session: LegacyAnnotationSession):
    """Legacy endpoint - Save annotation session to JSONL and audio to separate file."""
    try:
        session_data = session.model_dump()
        audio_filename = None

        if session.audio and session.audio.data_base64:
            audio_filename = f"{session.session_id}.webm"
            audio_path = AUDIO_DIR / audio_filename
            audio_bytes = base64.b64decode(session.audio.data_base64)
            audio_path.write_bytes(audio_bytes)
            session_data["audio"] = {
                "format": session.audio.format,
                "filename": audio_filename,
                "duration_ms": session.audio.duration_ms
            }

        with open(ANNOTATIONS_FILE, "a") as f:
            f.write(json.dumps(session_data) + "\n")

        total_sessions = sum(1 for _ in open(ANNOTATIONS_FILE)) if ANNOTATIONS_FILE.exists() else 1

        return {
            "status": "success",
            "session_id": session.session_id,
            "audio_saved": audio_filename is not None,
            "total_sessions": total_sessions
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config():
    """Get application configuration."""
    return load_config()


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


# Page routes
@app.get("/login")
async def login_page(request: Request):
    """Render login page."""
    user = await get_current_user_optional(request)
    if user:
        # Already logged in, redirect based on role
        if user["role"] == "admin":
            return RedirectResponse(url="/admin", status_code=302)
        return RedirectResponse(url="/specialist", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/admin")
async def admin_dashboard(request: Request):
    """Render admin dashboard."""
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user["role"] != "admin":
        return RedirectResponse(url="/specialist", status_code=302)

    return templates.TemplateResponse("admin/dashboard.html", {"request": request, "user": user})


@app.get("/admin/experiments/new")
async def admin_new_experiment(request: Request):
    """Render new experiment page."""
    user = await get_current_user_optional(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("admin/experiment_new.html", {"request": request, "user": user})


@app.get("/admin/experiments/{experiment_id}")
async def admin_experiment_detail(request: Request, experiment_id: int):
    """Render experiment detail page."""
    user = await get_current_user_optional(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        "admin/experiment_detail.html",
        {"request": request, "user": user, "experiment_id": experiment_id}
    )


@app.get("/admin/experiments/{experiment_id}/progress")
async def admin_experiment_progress(request: Request, experiment_id: int):
    """Render experiment progress page."""
    user = await get_current_user_optional(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        "admin/experiment_progress.html",
        {"request": request, "user": user, "experiment_id": experiment_id}
    )


@app.get("/specialist")
async def specialist_dashboard(request: Request):
    """Render specialist dashboard."""
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("specialist/dashboard.html", {"request": request, "user": user})


@app.get("/annotate/{experiment_id}")
async def annotate_page(request: Request, experiment_id: int):
    """Render annotation interface for an experiment."""
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(
        "specialist/annotate.html",
        {"request": request, "user": user, "experiment_id": experiment_id}
    )


# Serve static files
app.mount("/sample_images", StaticFiles(directory=BASE_DIR / "sample_images"), name="sample_images")
app.mount("/assets", StaticFiles(directory=BASE_DIR / "assets"), name="assets")
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend" / "static"), name="static")
app.mount("/prototype", StaticFiles(directory=BASE_DIR / "prototype", html=True), name="prototype")


@app.get("/")
async def root(request: Request):
    """Root redirect to appropriate dashboard or login."""
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user["role"] == "admin":
        return RedirectResponse(url="/admin", status_code=302)
    return RedirectResponse(url="/specialist", status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
