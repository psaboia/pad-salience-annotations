"""Specialist API router."""

import base64
import uuid
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, Depends

from ..database import (
    get_db_context,
    get_assignment,
    get_specialist_assignments,
    get_specialist_sample_order,
    start_assignment,
    generate_specialist_order,
    get_assignment_progress,
    create_annotation_session,
    get_session_by_uuid,
    get_current_session_for_assignment,
    complete_session,
    save_annotations,
    get_sample_tags_by_position,
)
from ..models import (
    AssignmentResponse,
    AnnotationSessionComplete,
    SessionProgressResponse,
)
from ..models.annotations import SampleInfo, SampleTags
from ..services.auth import require_specialist

router = APIRouter(prefix="/api/specialist", tags=["specialist"])

# Audio storage path
BASE_DIR = Path(__file__).parent.parent.parent
AUDIO_DIR = BASE_DIR / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/experiments")
async def list_my_experiments(user: dict = Depends(require_specialist)):
    """Get all experiments assigned to the current specialist."""
    async with get_db_context() as db:
        assignments = await get_specialist_assignments(db, user["id"])

        result = []
        for a in assignments:
            progress = await get_assignment_progress(db, a["id"]) if a["status"] != "pending" else None
            result.append({
                "assignment": AssignmentResponse(**a).model_dump(),
                "progress": progress
            })

        return result


@router.post("/experiments/{experiment_id}/start")
async def start_experiment(experiment_id: int, user: dict = Depends(require_specialist)):
    """Start working on an experiment (generates randomized order)."""
    async with get_db_context() as db:
        assignment = await get_assignment(db, experiment_id, user["id"])
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if assignment["status"] == "completed":
            raise HTTPException(status_code=400, detail="Experiment already completed")

        if assignment["status"] == "in_progress":
            # Already started, return current progress
            progress = await get_assignment_progress(db, assignment["id"])
            return {
                "status": "already_started",
                "assignment_id": assignment["id"],
                "progress": progress
            }

        # Generate randomization seed from timestamp
        seed = int(time.time() * 1000) + user["id"]

        # Start the assignment
        await start_assignment(db, assignment["id"], seed)

        # Generate randomized sample order
        await generate_specialist_order(db, assignment["id"], seed)

        return {
            "status": "started",
            "assignment_id": assignment["id"],
            "randomization_seed": seed
        }


@router.get("/experiments/{experiment_id}/current", response_model=SessionProgressResponse)
async def get_current_sample(experiment_id: int, user: dict = Depends(require_specialist)):
    """Get the current sample to annotate for an experiment."""
    async with get_db_context() as db:
        assignment = await get_assignment(db, experiment_id, user["id"])
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if assignment["status"] == "pending":
            raise HTTPException(
                status_code=400,
                detail="Experiment not started. Call /start first."
            )

        progress = await get_assignment_progress(db, assignment["id"])

        if assignment["status"] == "completed" or progress["remaining"] == 0:
            return SessionProgressResponse(
                current_position=progress["total"],
                total_samples=progress["total"],
                completed=progress["completed"],
                percentage=100.0,
                is_complete=True
            )

        # Get current session data
        current = await get_current_session_for_assignment(db, assignment["id"])
        if not current:
            # All done
            return SessionProgressResponse(
                current_position=progress["total"],
                total_samples=progress["total"],
                completed=progress["completed"],
                percentage=100.0,
                is_complete=True
            )

        # Create session if needed
        session_uuid = current.get("session_uuid")
        session_id = current.get("session_id")

        if not session_uuid:
            session_uuid = str(uuid.uuid4())
            session_id = await create_annotation_session(
                db,
                assignment_id=assignment["id"],
                experiment_sample_id=current["experiment_sample_id"],
                session_uuid=session_uuid
            )

        # Get tags for current sample
        tags_dict = await get_sample_tags_by_position(db, current["sample_id"])
        sample_tags = SampleTags(
            top_left=tags_dict.get("top-left"),
            top_right=tags_dict.get("top-right"),
            bottom_left=tags_dict.get("bottom-left"),
            bottom_right=tags_dict.get("bottom-right")
        ) if tags_dict else None

        sample = SampleInfo(
            id=current["sample_id"],
            drug_name=current["drug_name"],
            drug_name_display=current["drug_name_display"],
            card_id=current["card_id"],
            filename=current["filename"],
            image_path=current["image_path"],
            tags=sample_tags
        )

        # Get next sample info for confirmation dialog
        next_sample = None
        all_samples = await get_specialist_sample_order(db, assignment["id"])
        current_order = current.get("specialist_order", 1)
        if current_order < len(all_samples):
            next_s = all_samples[current_order]  # 0-indexed, current_order is 1-indexed
            # Get tags for next sample
            next_tags_dict = await get_sample_tags_by_position(db, next_s.get("sample_id", next_s["id"]))
            next_sample_tags = SampleTags(
                top_left=next_tags_dict.get("top-left"),
                top_right=next_tags_dict.get("top-right"),
                bottom_left=next_tags_dict.get("bottom-left"),
                bottom_right=next_tags_dict.get("bottom-right")
            ) if next_tags_dict else None

            next_sample = SampleInfo(
                id=next_s.get("sample_id", next_s["id"]),
                drug_name=next_s["drug_name"],
                drug_name_display=next_s["drug_name_display"],
                card_id=next_s["card_id"],
                filename=next_s["filename"],
                image_path=next_s["image_path"],
                tags=next_sample_tags
            )

        return SessionProgressResponse(
            session_uuid=session_uuid,
            session_id=session_id,
            sample=sample,
            current_position=current_order,
            total_samples=progress["total"],
            completed=progress["completed"],
            percentage=progress["percentage"],
            is_complete=False,
            next_sample=next_sample
        )


@router.post("/sessions/{session_uuid}/complete")
async def complete_annotation_session(
    session_uuid: str,
    data: AnnotationSessionComplete,
    user: dict = Depends(require_specialist)
):
    """Complete an annotation session and save data."""
    async with get_db_context() as db:
        session = await get_session_by_uuid(db, session_uuid)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session["status"] == "completed":
            raise HTTPException(status_code=400, detail="Session already completed")

        # Verify user owns this session
        cursor = await db.execute(
            """
            SELECT a.specialist_id
            FROM annotation_sessions ans
            JOIN assignments a ON ans.assignment_id = a.id
            WHERE ans.id = ?
            """,
            (session["id"],)
        )
        row = await cursor.fetchone()
        if not row or row["specialist_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Not your session")

        # Save audio file if present
        audio_filename = None
        audio_duration_ms = None
        if data.audio and data.audio.data_base64:
            audio_filename = f"{session_uuid}.webm"
            audio_path = AUDIO_DIR / audio_filename
            audio_bytes = base64.b64decode(data.audio.data_base64)
            audio_path.write_bytes(audio_bytes)
            audio_duration_ms = data.audio.duration_ms

        # Save annotations
        await save_annotations(
            db,
            session["id"],
            [ann.model_dump() for ann in data.annotations]
        )

        # Complete session
        await complete_session(
            db,
            session["id"],
            audio_filename=audio_filename,
            audio_duration_ms=audio_duration_ms,
            image_dimensions=data.image_dimensions.model_dump(),
            layout_settings=data.layout_settings.model_dump() if data.layout_settings else {}
        )

        # Get updated progress
        cursor = await db.execute(
            "SELECT assignment_id FROM annotation_sessions WHERE id = ?",
            (session["id"],)
        )
        row = await cursor.fetchone()
        progress = await get_assignment_progress(db, row["assignment_id"])

        # Check if all samples are complete
        if progress["remaining"] == 0:
            await db.execute(
                "UPDATE assignments SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
                (row["assignment_id"],)
            )
            await db.commit()

        return {
            "status": "success",
            "session_id": session["id"],
            "annotation_count": len(data.annotations),
            "audio_saved": audio_filename is not None,
            "progress": progress
        }


@router.get("/experiments/{experiment_id}/progress")
async def get_my_progress(experiment_id: int, user: dict = Depends(require_specialist)):
    """Get progress for a specific experiment."""
    async with get_db_context() as db:
        assignment = await get_assignment(db, experiment_id, user["id"])
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if assignment["status"] == "pending":
            return {
                "status": "pending",
                "message": "Experiment not started yet"
            }

        progress = await get_assignment_progress(db, assignment["id"])
        return {
            "status": assignment["status"],
            "progress": progress
        }
