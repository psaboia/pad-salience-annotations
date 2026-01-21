"""Admin API router."""

import csv
import io
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import StreamingResponse
from typing import List
from pydantic import BaseModel
from PIL import Image

# Import AprilTag generator
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from generate_apriltags import generate_tag_image

from ..database import (
    get_db_context,
    get_all_samples,
    get_all_studies,
    get_study_by_id,
    create_study,
    update_study_status,
    add_samples_to_study,
    get_study_samples,
    get_specialists,
    create_assignment,
    get_study_assignments,
    get_study_progress,
    get_all_users,
    create_user,
    update_user,
    deactivate_user,
    get_user_by_id_include_inactive,
    get_user_by_email,
    get_user_roles,
    set_user_roles,
    get_sample_tags_by_position,
    allocate_tags_for_all_samples,
)
from ..models import (
    StudyCreate,
    StudyUpdate,
    StudyResponse,
    StudyWithSamples,
    SampleResponse,
    SampleSelectionRequest,
    AssignmentCreate,
    AssignmentResponse,
)
from ..models.auth import UserCreate, UserUpdate, UserResponse
from ..models.studies import SampleInStudy, AssignmentProgress
from ..services.auth import require_admin, require_super_admin, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Sample endpoints
@router.get("/samples", response_model=List[SampleResponse])
async def list_samples(_: dict = Depends(require_admin)):
    """Get all available samples."""
    async with get_db_context() as db:
        samples = await get_all_samples(db)
        return [SampleResponse(**s) for s in samples]


# Study endpoints
@router.get("/studies", response_model=List[StudyResponse])
async def list_studies(_: dict = Depends(require_admin)):
    """Get all studies."""
    async with get_db_context() as db:
        studies = await get_all_studies(db)
        return [StudyResponse(**s) for s in studies]


@router.post("/studies", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_study(data: StudyCreate, admin: dict = Depends(require_admin)):
    """Create a new study."""
    async with get_db_context() as db:
        study_id = await create_study(
            db,
            name=data.name,
            description=data.description,
            instructions=data.instructions,
            created_by=admin["id"],
            eyetracking_mode=data.eyetracking_mode or "disabled",
            annotation_mode=data.annotation_mode or "drawing",
            default_image_width=data.default_image_width,
            default_image_height=data.default_image_height
        )
        study = await get_study_by_id(db, study_id)
        return StudyResponse(**study)


@router.get("/studies/{study_id}", response_model=StudyWithSamples)
async def get_study(study_id: int, _: dict = Depends(require_admin)):
    """Get a specific study with its samples."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        samples = await get_study_samples(db, study_id)
        sample_models = [SampleInStudy(**s) for s in samples]

        return StudyWithSamples(
            **study,
            samples=sample_models,
            sample_count=len(sample_models)
        )


@router.put("/studies/{study_id}", response_model=StudyResponse)
async def update_study(study_id: int, data: StudyUpdate, _: dict = Depends(require_admin)):
    """Update a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        # Update fields
        if data.name is not None:
            await db.execute(
                "UPDATE studies SET name = ?, updated_at = datetime('now') WHERE id = ?",
                (data.name, study_id)
            )
        if data.description is not None:
            await db.execute(
                "UPDATE studies SET description = ?, updated_at = datetime('now') WHERE id = ?",
                (data.description, study_id)
            )
        if data.instructions is not None:
            await db.execute(
                "UPDATE studies SET instructions = ?, updated_at = datetime('now') WHERE id = ?",
                (data.instructions, study_id)
            )
        if data.eyetracking_mode is not None:
            await db.execute(
                "UPDATE studies SET eyetracking_mode = ?, updated_at = datetime('now') WHERE id = ?",
                (data.eyetracking_mode, study_id)
            )
        if data.default_image_width is not None:
            await db.execute(
                "UPDATE studies SET default_image_width = ?, updated_at = datetime('now') WHERE id = ?",
                (data.default_image_width, study_id)
            )
        if data.default_image_height is not None:
            await db.execute(
                "UPDATE studies SET default_image_height = ?, updated_at = datetime('now') WHERE id = ?",
                (data.default_image_height, study_id)
            )
        if data.status is not None:
            await update_study_status(db, study_id, data.status)
        else:
            await db.commit()

        study = await get_study_by_id(db, study_id)
        return StudyResponse(**study)


@router.delete("/studies/{study_id}")
async def delete_study(study_id: int, _: dict = Depends(require_admin)):
    """Delete a study (only if draft)."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] not in ("draft", "archived"):
            raise HTTPException(
                status_code=400,
                detail="Can only delete draft or archived studies"
            )

        await db.execute("DELETE FROM studies WHERE id = ?", (study_id,))
        await db.commit()

        return {"status": "success", "message": "Study deleted"}


@router.post("/studies/{study_id}/activate")
async def activate_study(study_id: int, _: dict = Depends(require_admin)):
    """Activate a study (move from draft to active)."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Can only activate draft studies"
            )

        # Check that study has samples
        samples = await get_study_samples(db, study_id)
        if not samples:
            raise HTTPException(
                status_code=400,
                detail="Cannot activate study without samples"
            )

        # Check that study has assignments
        assignments = await get_study_assignments(db, study_id)
        if not assignments:
            raise HTTPException(
                status_code=400,
                detail="Cannot activate study without specialist assignments"
            )

        await update_study_status(db, study_id, "active")

        return {"status": "success", "message": "Study activated"}


@router.post("/studies/{study_id}/pause")
async def pause_study(study_id: int, _: dict = Depends(require_admin)):
    """Pause an active study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] != "active":
            raise HTTPException(
                status_code=400,
                detail="Can only pause active studies"
            )

        await update_study_status(db, study_id, "paused")

        return {"status": "success", "message": "Study paused"}


@router.post("/studies/{study_id}/resume")
async def resume_study(study_id: int, _: dict = Depends(require_admin)):
    """Resume a paused study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] != "paused":
            raise HTTPException(
                status_code=400,
                detail="Can only resume paused studies"
            )

        await update_study_status(db, study_id, "active")

        return {"status": "success", "message": "Study resumed"}


# Sample management for studies
@router.get("/studies/{study_id}/samples", response_model=List[SampleInStudy])
async def get_study_sample_list(study_id: int, _: dict = Depends(require_admin)):
    """Get samples assigned to a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        samples = await get_study_samples(db, study_id)
        return [SampleInStudy(**s) for s in samples]


@router.post("/studies/{study_id}/samples")
async def set_study_samples(
    study_id: int,
    data: SampleSelectionRequest,
    _: dict = Depends(require_admin)
):
    """Set the samples for a study (replaces existing)."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Can only modify samples for draft studies"
            )

        # Clear existing samples
        await db.execute(
            "DELETE FROM study_samples WHERE study_id = ?",
            (study_id,)
        )
        await db.commit()

        # Add new samples
        await add_samples_to_study(db, study_id, data.sample_ids)

        return {"status": "success", "sample_count": len(data.sample_ids)}


# Specialist management
@router.get("/specialists", response_model=List[dict])
async def list_specialists(_: dict = Depends(require_admin)):
    """Get all specialists."""
    async with get_db_context() as db:
        specialists = await get_specialists(db)
        return [
            {
                "id": s["id"],
                "email": s["email"],
                "name": s["name"],
                "expertise_level": s.get("expertise_level"),
                "is_active": bool(s["is_active"])
            }
            for s in specialists
        ]


# User management endpoints
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    include_inactive: bool = Query(False, description="Include inactive users"),
    _: dict = Depends(require_admin)
):
    """Get all users."""
    async with get_db_context() as db:
        users = await get_all_users(db, include_inactive=include_inactive)
        result = []
        for u in users:
            roles = await get_user_roles(db, u["id"])
            # Fallback if user_roles is empty
            if not roles:
                roles = [u["role"]]
            result.append(UserResponse(
                id=u["id"],
                email=u["email"],
                name=u["name"],
                role=u["role"],
                roles=roles,
                expertise_level=u.get("expertise_level"),
                years_experience=u.get("years_experience"),
                training_date=u.get("training_date"),
                institution=u.get("institution"),
                specializations=u.get("specializations"),
                is_active=bool(u["is_active"]),
                created_at=u.get("created_at")
            ))
        return result


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(data: UserCreate, _: dict = Depends(require_super_admin)):
    """Create a new user (super_admin only)."""
    async with get_db_context() as db:
        # Check if email already exists
        existing = await get_user_by_email(db, data.email)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )

        password_hash = hash_password(data.password)

        # For the legacy users.role field, map super_admin to admin
        # (the users table constraint only allows 'admin' or 'specialist')
        legacy_role = data.role
        if legacy_role == 'super_admin':
            legacy_role = 'admin'

        user_id = await create_user(
            db,
            email=data.email,
            name=data.name,
            password_hash=password_hash,
            role=legacy_role,
            expertise_level=data.expertise_level,
            years_experience=data.years_experience,
            training_date=data.training_date,
            institution=data.institution,
            specializations=data.specializations
        )

        # If the actual role is super_admin, update user_roles table
        if data.role == 'super_admin':
            await set_user_roles(db, user_id, ['super_admin'])

        user = await get_user_by_id_include_inactive(db, user_id)
        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            expertise_level=user.get("expertise_level"),
            years_experience=user.get("years_experience"),
            training_date=user.get("training_date"),
            institution=user.get("institution"),
            specializations=user.get("specializations"),
            is_active=bool(user["is_active"]),
            created_at=user.get("created_at")
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, _: dict = Depends(require_admin)):
    """Get a specific user."""
    async with get_db_context() as db:
        user = await get_user_by_id_include_inactive(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            expertise_level=user.get("expertise_level"),
            years_experience=user.get("years_experience"),
            training_date=user.get("training_date"),
            institution=user.get("institution"),
            specializations=user.get("specializations"),
            is_active=bool(user["is_active"]),
            created_at=user.get("created_at")
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_existing_user(user_id: int, data: UserUpdate, _: dict = Depends(require_super_admin)):
    """Update a user (super_admin only)."""
    async with get_db_context() as db:
        user = await get_user_by_id_include_inactive(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if email is being changed and already exists
        if data.email and data.email != user["email"]:
            existing = await get_user_by_email(db, data.email)
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail="User with this email already exists"
                )

        # Hash password if being changed
        password_hash = None
        if data.password:
            password_hash = hash_password(data.password)

        # For the legacy users.role field, map super_admin to admin
        # (the users table constraint only allows 'admin' or 'specialist')
        legacy_role = None
        if data.roles:
            # Determine legacy role from roles list
            if 'super_admin' in data.roles or 'admin' in data.roles:
                legacy_role = 'admin'
            elif 'specialist' in data.roles:
                legacy_role = 'specialist'
        elif data.role:
            legacy_role = data.role
            if legacy_role == 'super_admin':
                legacy_role = 'admin'

        await update_user(
            db,
            user_id=user_id,
            email=data.email,
            name=data.name,
            password_hash=password_hash,
            role=legacy_role,
            expertise_level=data.expertise_level,
            years_experience=data.years_experience,
            training_date=data.training_date,
            institution=data.institution,
            specializations=data.specializations,
            is_active=data.is_active
        )

        # Update user_roles table
        if data.roles:
            # If roles list is provided, replace all roles
            await set_user_roles(db, user_id, data.roles)
        elif data.role:
            # Legacy: if single role is provided, add it to existing roles
            current_roles = await get_user_roles(db, user_id)
            if data.role not in current_roles:
                new_roles = list(set(current_roles + [data.role]))
                await set_user_roles(db, user_id, new_roles)

        user = await get_user_by_id_include_inactive(db, user_id)
        roles = await get_user_roles(db, user_id)
        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            roles=roles,
            expertise_level=user.get("expertise_level"),
            years_experience=user.get("years_experience"),
            training_date=user.get("training_date"),
            institution=user.get("institution"),
            specializations=user.get("specializations"),
            is_active=bool(user["is_active"]),
            created_at=user.get("created_at")
        )


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_super_admin)):
    """Deactivate a user (super_admin only, soft delete)."""
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate your own account"
        )

    async with get_db_context() as db:
        user = await get_user_by_id_include_inactive(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if user is a super_admin
        user_roles = await get_user_roles(db, user_id)
        if "super_admin" in user_roles:
            # Count active super_admins
            cursor = await db.execute(
                """
                SELECT COUNT(DISTINCT u.id) as count
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                WHERE ur.role = 'super_admin' AND u.is_active = 1
                """
            )
            row = await cursor.fetchone()
            active_super_admin_count = row[0] if row else 0

            if active_super_admin_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot deactivate the last active super admin"
                )

        await deactivate_user(db, user_id)

        return {"status": "success", "message": "User deactivated"}


# Assignment management
@router.get("/studies/{study_id}/assignments", response_model=List[AssignmentResponse])
async def get_assignments(study_id: int, _: dict = Depends(require_admin)):
    """Get all assignments for a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        assignments = await get_study_assignments(db, study_id)
        return [AssignmentResponse(**a) for a in assignments]


@router.post("/studies/{study_id}/assignments", response_model=AssignmentResponse)
async def create_new_assignment(
    study_id: int,
    data: AssignmentCreate,
    _: dict = Depends(require_admin)
):
    """Assign a specialist to a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] not in ("draft", "active"):
            raise HTTPException(
                status_code=400,
                detail="Cannot add assignments to this study"
            )

        # Fetch specialist profile for snapshot
        specialist = await get_user_by_id_include_inactive(db, data.specialist_id)
        if not specialist:
            raise HTTPException(status_code=404, detail="Specialist not found")

        try:
            assignment_id = await create_assignment(
                db,
                study_id,
                data.specialist_id,
                expertise_level_snapshot=specialist.get("expertise_level"),
                years_experience_snapshot=specialist.get("years_experience"),
                training_date_snapshot=specialist.get("training_date")
            )
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(
                    status_code=400,
                    detail="Specialist already assigned to this study"
                )
            raise

        assignments = await get_study_assignments(db, study_id)
        assignment = next((a for a in assignments if a["id"] == assignment_id), None)

        return AssignmentResponse(**assignment)


@router.get("/studies/{study_id}/assignments/{specialist_id}/stats")
async def get_assignment_stats(
    study_id: int,
    specialist_id: int,
    _: dict = Depends(require_admin)
):
    """Get statistics for an assignment (annotation count, etc.)."""
    async with get_db_context() as db:
        # Get assignment
        cursor = await db.execute(
            "SELECT id FROM assignments WHERE study_id = ? AND specialist_id = ?",
            (study_id, specialist_id)
        )
        assignment = await cursor.fetchone()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        assignment_id = assignment["id"]

        # Count completed sessions
        cursor = await db.execute(
            """
            SELECT COUNT(*) as count FROM annotation_sessions
            WHERE assignment_id = ? AND status = 'completed'
            """,
            (assignment_id,)
        )
        row = await cursor.fetchone()
        completed_sessions = row["count"] if row else 0

        # Count total annotations
        cursor = await db.execute(
            """
            SELECT COUNT(*) as count FROM annotations a
            JOIN annotation_sessions s ON a.session_id = s.id
            WHERE s.assignment_id = ?
            """,
            (assignment_id,)
        )
        row = await cursor.fetchone()
        total_annotations = row["count"] if row else 0

        return {
            "completed_sessions": completed_sessions,
            "total_annotations": total_annotations
        }


@router.delete("/studies/{study_id}/assignments/{specialist_id}")
async def delete_assignment(
    study_id: int,
    specialist_id: int,
    _: dict = Depends(require_admin)
):
    """Remove a specialist from a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        if study["status"] not in ("draft", "active", "paused"):
            raise HTTPException(
                status_code=400,
                detail="Can only remove assignments from draft, active, or paused studies"
            )

        await db.execute(
            "DELETE FROM assignments WHERE study_id = ? AND specialist_id = ?",
            (study_id, specialist_id)
        )
        await db.commit()

        return {"status": "success", "message": "Assignment removed"}


# Progress tracking
@router.get("/studies/{study_id}/progress")
async def get_progress(study_id: int, _: dict = Depends(require_admin)):
    """Get detailed progress for a study."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        progress = await get_study_progress(db, study_id)
        progress["study"] = StudyResponse(**study).model_dump()

        return progress


# Replay endpoints
@router.get("/studies/{study_id}/completed-sessions")
async def get_completed_sessions(study_id: int, _: dict = Depends(require_admin)):
    """Get all completed annotation sessions for a study."""
    async with get_db_context() as db:
        cursor = await db.execute(
            """
            SELECT
                ans.id as session_id,
                ans.session_uuid,
                ans.audio_filename,
                ans.audio_duration_ms,
                ans.completed_at,
                a.specialist_id,
                u.name as specialist_name,
                s.drug_name_display,
                s.card_id,
                (SELECT COUNT(*) FROM annotations ann WHERE ann.session_id = ans.id) as annotation_count
            FROM annotation_sessions ans
            JOIN assignments a ON ans.assignment_id = a.id
            JOIN users u ON a.specialist_id = u.id
            JOIN study_samples ss ON ans.study_sample_id = ss.id
            JOIN samples s ON ss.sample_id = s.id
            WHERE a.study_id = ? AND ans.status = 'completed'
            ORDER BY ans.completed_at DESC
            """,
            (study_id,)
        )
        rows = await cursor.fetchall()

        return [
            {
                "session_id": row["session_id"],
                "session_uuid": row["session_uuid"],
                "has_audio": row["audio_filename"] is not None,
                "has_annotations": row["annotation_count"] > 0,
                "audio_duration_ms": row["audio_duration_ms"],
                "completed_at": row["completed_at"],
                "specialist_id": row["specialist_id"],
                "specialist_name": row["specialist_name"],
                "drug_name_display": row["drug_name_display"],
                "card_id": row["card_id"]
            }
            for row in rows
        ]


@router.get("/sessions/{session_id}/replay-data")
async def get_session_replay_data(session_id: int, _: dict = Depends(require_admin)):
    """Get all data needed to replay an annotation session."""
    async with get_db_context() as db:
        # Get session with assignment, specialist, and sample info
        cursor = await db.execute(
            """
            SELECT
                ans.id as session_id,
                ans.session_uuid,
                ans.status as session_status,
                ans.audio_filename,
                ans.audio_duration_ms,
                ans.image_dimensions_json,
                ans.layout_settings_json,
                ans.completed_at,
                a.id as assignment_id,
                a.study_id,
                st.name as study_name,
                st.eyetracking_mode,
                u.id as specialist_id,
                u.name as specialist_name,
                u.email as specialist_email,
                ss.sample_id,
                s.drug_name,
                s.drug_name_display,
                s.card_id,
                s.image_path
            FROM annotation_sessions ans
            JOIN assignments a ON ans.assignment_id = a.id
            JOIN studies st ON a.study_id = st.id
            JOIN users u ON a.specialist_id = u.id
            JOIN study_samples ss ON ans.study_sample_id = ss.id
            JOIN samples s ON ss.sample_id = s.id
            WHERE ans.id = ?
            """,
            (session_id,)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        session = dict(row)

        # Parse JSON fields
        import json
        if session.get('image_dimensions_json'):
            session['image_dimensions'] = json.loads(session['image_dimensions_json'])
        else:
            session['image_dimensions'] = None
        del session['image_dimensions_json']

        if session.get('layout_settings_json'):
            session['layout_settings'] = json.loads(session['layout_settings_json'])
        else:
            session['layout_settings'] = None
        del session['layout_settings_json']

        # Get annotations for this session
        cursor = await db.execute(
            """
            SELECT
                id,
                annotation_type as type,
                color,
                lanes_json,
                bbox_normalized_json,
                points_normalized_json,
                timestamp_start_ms,
                timestamp_end_ms
            FROM annotations
            WHERE session_id = ?
            ORDER BY timestamp_start_ms, id
            """,
            (session_id,)
        )
        rows = await cursor.fetchall()

        annotations = []
        for ann_row in rows:
            ann = dict(ann_row)
            # Parse JSON fields
            if ann.get('lanes_json'):
                ann['lanes'] = json.loads(ann['lanes_json'])
            else:
                ann['lanes'] = []
            del ann['lanes_json']

            if ann.get('bbox_normalized_json'):
                ann['bbox_normalized'] = json.loads(ann['bbox_normalized_json'])
            else:
                ann['bbox_normalized'] = None
            del ann['bbox_normalized_json']

            if ann.get('points_normalized_json'):
                ann['points_normalized'] = json.loads(ann['points_normalized_json'])
            else:
                ann['points_normalized'] = None
            del ann['points_normalized_json']

            annotations.append(ann)

        # Build audio URL if available
        audio_url = None
        if session.get('audio_filename'):
            audio_url = f"/data/audio/{session['audio_filename']}"

        # Get navigation info (previous/next sessions for same specialist in same study)
        cursor = await db.execute(
            """
            SELECT ans.id as session_id
            FROM annotation_sessions ans
            JOIN assignments a ON ans.assignment_id = a.id
            WHERE a.study_id = ?
              AND a.specialist_id = ?
              AND ans.status = 'completed'
            ORDER BY ans.completed_at, ans.id
            """,
            (session['study_id'], session['specialist_id'])
        )
        all_sessions = [row['session_id'] for row in await cursor.fetchall()]

        # Find current position and determine prev/next
        current_index = all_sessions.index(session_id) if session_id in all_sessions else -1
        total_sessions = len(all_sessions)
        previous_session_id = all_sessions[current_index - 1] if current_index > 0 else None
        next_session_id = all_sessions[current_index + 1] if current_index < total_sessions - 1 else None

        # Get sample tags for AprilTag display in replay
        sample_tags = await get_sample_tags_by_position(db, session['sample_id'])

        return {
            "session": {
                "id": session['session_id'],
                "uuid": session['session_uuid'],
                "status": session['session_status'],
                "completed_at": session['completed_at'],
                "audio_duration_ms": session['audio_duration_ms'],
                "image_dimensions": session['image_dimensions'],
                "layout_settings": session['layout_settings']
            },
            "specialist": {
                "id": session['specialist_id'],
                "name": session['specialist_name'],
                "email": session['specialist_email']
            },
            "sample": {
                "drug_name": session['drug_name'],
                "drug_name_display": session['drug_name_display'],
                "card_id": session['card_id'],
                "image_path": session['image_path'],
                "tags": sample_tags
            },
            "study": {
                "id": session['study_id'],
                "name": session['study_name'],
                "eyetracking_mode": session['eyetracking_mode']
            },
            "annotations": annotations,
            "audio_url": audio_url,
            "navigation": {
                "current_index": current_index + 1,
                "total_sessions": total_sessions,
                "previous_session_id": previous_session_id,
                "next_session_id": next_session_id
            }
        }


# Dashboard endpoints
@router.get("/dashboard/activity")
async def get_recent_activity(_: dict = Depends(require_admin)):
    """Get recent annotation activity for dashboard."""
    async with get_db_context() as db:
        cursor = await db.execute(
            """
            SELECT
                s.id as session_id,
                s.completed_at,
                u.name as specialist_name,
                st.id as study_id,
                st.name as study_name
            FROM annotation_sessions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN users u ON a.specialist_id = u.id
            JOIN studies st ON a.study_id = st.id
            WHERE s.status = 'completed' AND s.completed_at IS NOT NULL
            ORDER BY s.completed_at DESC
            LIMIT 10
            """
        )
        rows = await cursor.fetchall()

        return [
            {
                "session_id": row["session_id"],
                "study_id": row["study_id"],
                "completed_at": row["completed_at"],
                "specialist_name": row["specialist_name"],
                "study_name": row["study_name"]
            }
            for row in rows
        ]


# PAD Analytics integration endpoints
class PADImportRequest(BaseModel):
    project_id: int
    project_name: str
    samples_per_drug: int = 1  # Number of samples (different sample_id) per drug


@router.get("/pad-projects")
async def list_pad_projects(_: dict = Depends(require_admin)):
    """List available PAD projects from pad-analytics."""
    try:
        import pad_analytics as pad

        projects = pad.get_projects()
        return [
            {
                "id": int(row["id"]),
                "name": row["project_name"],
                "annotation": row.get("annotation", "")
            }
            for _, row in projects.iterrows()
            if row["project_name"]  # Filter out empty names
        ]
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="pad-analytics library is not installed"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch PAD projects: {str(e)}"
        )


@router.post("/pad-import")
async def import_pad_samples(
    data: PADImportRequest,
    _: dict = Depends(require_admin)
):
    """Import one sample per drug from a PAD project."""
    try:
        import pad_analytics as pad
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="pad-analytics library is not installed"
        )

    import httpx
    from pathlib import Path

    # Get cards from project
    try:
        cards = pad.get_project_cards(data.project_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch project cards: {str(e)}"
        )

    # Filter valid cards (not deleted, quantity=100%)
    valid_cards = cards[(cards['deleted'] == False) & (cards['quantity'] == 100)].copy()

    if valid_cards.empty:
        raise HTTPException(
            status_code=400,
            detail="No valid cards found in project (need quantity=100% and not deleted)"
        )

    # Normalize drug names
    valid_cards['drug_normalized'] = valid_cards['sample_name'].str.lower().str.strip()

    # Select N samples per drug with different sample_ids
    # First, get one card per (drug, sample_id) combination
    unique_samples = valid_cards.groupby(['drug_normalized', 'sample_id']).first().reset_index()

    # Then select up to N different sample_ids per drug
    samples_per_drug = data.samples_per_drug
    selected_samples = []
    for drug in unique_samples['drug_normalized'].unique():
        drug_samples = unique_samples[unique_samples['drug_normalized'] == drug]
        # Take up to N samples with different sample_ids
        selected = drug_samples.head(samples_per_drug)
        selected_samples.append(selected)

    if not selected_samples:
        raise HTTPException(
            status_code=400,
            detail="No valid samples found after filtering"
        )

    import pandas as pd
    samples_to_import = pd.concat(selected_samples, ignore_index=True)

    # Download images and create samples
    samples_dir = Path("sample_images")
    samples_dir.mkdir(exist_ok=True)

    imported_samples = []
    async with httpx.AsyncClient() as client:
        for _, card in samples_to_import.iterrows():
            # Build image URL from processed_file_location
            processed_path = card['processed_file_location']
            # Convert /var/www/html/images/... to https://pad.crc.nd.edu/images/...
            relative_path = processed_path.replace('/var/www/html/', '')
            image_url = f"https://pad.crc.nd.edu/{relative_path}"

            # Clean drug name for filename
            drug_name = card['drug_normalized'].replace(' ', '-').replace('(', '').replace(')', '')
            filename = f"{drug_name}_{card['id']}_processed.png"
            local_path = samples_dir / filename

            try:
                response = await client.get(image_url, timeout=30.0)
                response.raise_for_status()
                local_path.write_bytes(response.content)

                imported_samples.append({
                    "drug_name": drug_name,
                    "drug_name_display": card['sample_name'].title(),
                    "card_id": int(card['id']),
                    "pad_sample_id": int(card['sample_id']),
                    "quantity": int(card['quantity']),
                    "filename": filename,
                    "path": f"sample_images/{filename}",
                    "image_type": "processed"
                })
            except Exception as e:
                print(f"Failed to download {image_url}: {e}")
                continue

    if not imported_samples:
        raise HTTPException(
            status_code=500,
            detail="Failed to download any images from the project"
        )

    # Save to database - REPLACE samples not used in any study
    async with get_db_context() as db:
        # Delete tags for samples that will be deleted
        await db.execute("""
            DELETE FROM sample_tags
            WHERE sample_id NOT IN (SELECT DISTINCT sample_id FROM study_samples)
        """)

        # Only delete samples that are not referenced by any study
        await db.execute("""
            DELETE FROM samples
            WHERE id NOT IN (SELECT DISTINCT sample_id FROM study_samples)
        """)

        # Insert new samples
        for sample in imported_samples:
            await db.execute("""
                INSERT INTO samples
                (drug_name, drug_name_display, card_id, pad_sample_id, quantity, filename, image_path, image_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sample['drug_name'],
                sample['drug_name_display'],
                sample['card_id'],
                sample['pad_sample_id'],
                sample['quantity'],
                sample['filename'],
                sample['path'],
                sample['image_type']
            ))
        await db.commit()

        # Allocate AprilTags for eye-tracking
        tags_allocated = await allocate_tags_for_all_samples(db)

    return {
        "imported": len(imported_samples),
        "tags_allocated": tags_allocated,
        "project_name": data.project_name,
        "samples": imported_samples
    }


@router.post("/pad-backfill-sample-ids")
async def backfill_pad_sample_ids(
    data: PADImportRequest,
    _: dict = Depends(require_admin)
):
    """Backfill pad_sample_id for existing samples by querying PAD Analytics using card_id."""
    try:
        import pad_analytics as pad
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="pad-analytics library is not installed"
        )

    # Get cards from project
    try:
        cards = pad.get_project_cards(data.project_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch project cards: {str(e)}"
        )

    # Create a mapping from card_id to sample_id
    card_to_sample = {}
    for _, card in cards.iterrows():
        card_to_sample[int(card['id'])] = int(card['sample_id'])

    # Update samples in database
    updated_count = 0
    async with get_db_context() as db:
        # Get all samples that have a card_id but no pad_sample_id
        cursor = await db.execute(
            "SELECT id, card_id FROM samples WHERE card_id IS NOT NULL AND (pad_sample_id IS NULL OR pad_sample_id = 0)"
        )
        rows = await cursor.fetchall()

        for row in rows:
            card_id = row["card_id"]
            if card_id in card_to_sample:
                pad_sample_id = card_to_sample[card_id]
                await db.execute(
                    "UPDATE samples SET pad_sample_id = ? WHERE id = ?",
                    (pad_sample_id, row["id"])
                )
                updated_count += 1

        await db.commit()

    return {
        "updated": updated_count,
        "project_name": data.project_name,
        "message": f"Updated {updated_count} samples with pad_sample_id from PAD Analytics"
    }


# Study metadata export (for replication)
@router.get("/studies/{study_id}/export-metadata")
async def export_study_metadata(study_id: int, _: dict = Depends(require_admin)):
    """Export study metadata as ZIP containing metadata.csv and resized images."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        # Get default dimensions from study for fallback
        study_default_width = study.get("default_image_width")
        study_default_height = study.get("default_image_height")

        # Query samples with image dimensions from first completed session
        # Uses subquery to get only the first completed session per sample
        cursor = await db.execute(
            """
            SELECT
                s.id as sample_id,
                s.pad_sample_id,
                s.card_id,
                s.drug_name,
                s.drug_name_display,
                s.image_path,
                s.filename,
                first_session.image_dimensions_json
            FROM study_samples ss
            JOIN samples s ON ss.sample_id = s.id
            LEFT JOIN (
                SELECT
                    ans.study_sample_id,
                    ans.image_dimensions_json
                FROM annotation_sessions ans
                WHERE ans.status = 'completed'
                  AND ans.id = (
                      SELECT MIN(ans2.id)
                      FROM annotation_sessions ans2
                      WHERE ans2.study_sample_id = ans.study_sample_id
                        AND ans2.status = 'completed'
                  )
            ) first_session ON first_session.study_sample_id = ss.id
            WHERE ss.study_id = ?
            ORDER BY s.drug_name_display
            """,
            (study_id,)
        )
        rows = await cursor.fetchall()

        if not rows:
            raise HTTPException(status_code=400, detail="No samples found in study")

        # Prepare CSV data
        csv_rows = []
        images_to_process = []

        for row in rows:
            sample_id = row["sample_id"]
            image_path = row["image_path"]
            filename = row["filename"]

            # Parse image dimensions with fallback to study defaults
            width = None
            height = None
            if row["image_dimensions_json"]:
                try:
                    dims = json.loads(row["image_dimensions_json"])
                    width = dims.get("width")
                    height = dims.get("height")
                except (json.JSONDecodeError, TypeError):
                    pass

            # Fallback to study default dimensions if no session dimensions
            if not width and study_default_width:
                width = study_default_width
            if not height and study_default_height:
                height = study_default_height

            # Get AprilTags for this sample
            tags = await get_sample_tags_by_position(db, sample_id)

            # Use pad_sample_id if available, otherwise use internal sample_id
            export_sample_id = row["pad_sample_id"] if row["pad_sample_id"] else sample_id
            csv_row = {
                "sample_id": export_sample_id,
                "card_id": row["card_id"],
                "drug_name": row["drug_name"],
                "image_width": width or "",
                "image_height": height or "",
                "tag_top_left": tags.get("top-left", ""),
                "tag_top_right": tags.get("top-right", ""),
                "tag_bottom_left": tags.get("bottom-left", ""),
                "tag_bottom_right": tags.get("bottom-right", ""),
                "image_filename": f"images/{filename}" if filename else ""
            }
            csv_rows.append(csv_row)

            # Add to images to process if we have dimensions and path
            if width and height and image_path:
                images_to_process.append({
                    "source_path": image_path,
                    "filename": filename,
                    "width": width,
                    "height": height
                })

    # Collect all unique tag IDs
    tag_ids = set()
    for row in csv_rows:
        for tag_col in ["tag_top_left", "tag_top_right", "tag_bottom_left", "tag_bottom_right"]:
            if row[tag_col] != "":
                tag_ids.add(int(row[tag_col]))

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Generate metadata.csv
        csv_buffer = io.StringIO()
        fieldnames = [
            "sample_id", "card_id", "drug_name",
            "image_width", "image_height",
            "tag_top_left", "tag_top_right", "tag_bottom_left", "tag_bottom_right",
            "image_filename"
        ]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
        zf.writestr("metadata.csv", csv_buffer.getvalue())

        # Process and add sample images
        for img_info in images_to_process:
            source_path = Path(img_info["source_path"])
            if not source_path.exists():
                continue

            try:
                with Image.open(source_path) as img:
                    # Resize to annotation dimensions
                    resized = img.resize(
                        (img_info["width"], img_info["height"]),
                        Image.Resampling.LANCZOS
                    )

                    # Save to bytes
                    img_buffer = io.BytesIO()
                    resized.save(img_buffer, format="PNG")
                    img_buffer.seek(0)

                    # Add to ZIP
                    zf.writestr(f"images/{img_info['filename']}", img_buffer.read())
            except Exception:
                # Skip images that fail to process
                continue

        # Generate and add AprilTag images
        for tag_id in sorted(tag_ids):
            try:
                tag_img = generate_tag_image(tag_id, size=100)
                tag_buffer = io.BytesIO()
                tag_img.save(tag_buffer, format="PNG")
                tag_buffer.seek(0)
                zf.writestr(f"tags/tag36h11_{tag_id}.png", tag_buffer.read())
            except Exception:
                # Skip tags that fail to generate
                continue

    zip_buffer.seek(0)

    # Generate filename
    study_name_clean = "".join(c if c.isalnum() or c in "-_" else "_" for c in study["name"])
    date_str = datetime.now().strftime("%Y%m%d")
    zip_filename = f"{study_name_clean}_metadata_{date_str}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )


# Study data export (for analysis)
@router.get("/studies/{study_id}/export-data")
async def export_study_data(study_id: int, _: dict = Depends(require_admin)):
    """Export complete study data as ZIP containing study_info.json, specialists.csv, sessions.csv, annotations.csv, and audio files."""
    async with get_db_context() as db:
        study = await get_study_by_id(db, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")

        # Get all specialists assigned to the study
        cursor = await db.execute(
            """
            SELECT DISTINCT
                u.id as specialist_id,
                u.name,
                u.email,
                a.expertise_level_snapshot as expertise_level,
                a.years_experience_snapshot as years_experience
            FROM assignments a
            JOIN users u ON a.specialist_id = u.id
            WHERE a.study_id = ?
            ORDER BY u.name
            """,
            (study_id,)
        )
        specialists_rows = await cursor.fetchall()

        # Get all sessions for the study
        cursor = await db.execute(
            """
            SELECT
                ans.id as session_id,
                ans.session_uuid,
                a.specialist_id,
                u.name as specialist_name,
                s.id as sample_id,
                s.pad_sample_id,
                s.drug_name,
                s.card_id,
                ans.status,
                ans.started_at,
                ans.completed_at,
                ans.audio_filename,
                ans.audio_duration_ms,
                ans.image_dimensions_json
            FROM annotation_sessions ans
            JOIN assignments a ON ans.assignment_id = a.id
            JOIN users u ON a.specialist_id = u.id
            JOIN study_samples ss ON ans.study_sample_id = ss.id
            JOIN samples s ON ss.sample_id = s.id
            WHERE a.study_id = ?
            ORDER BY ans.completed_at, ans.id
            """,
            (study_id,)
        )
        sessions_rows = await cursor.fetchall()

        # Get all annotations for the study
        cursor = await db.execute(
            """
            SELECT
                ann.id as annotation_id,
                ans.id as session_id,
                ans.session_uuid,
                u.name as specialist_name,
                s.drug_name,
                ann.annotation_type,
                ann.color,
                ann.lanes_json,
                ann.bbox_normalized_json,
                ann.points_normalized_json,
                ann.timestamp_start_ms,
                ann.timestamp_end_ms
            FROM annotations ann
            JOIN annotation_sessions ans ON ann.session_id = ans.id
            JOIN assignments a ON ans.assignment_id = a.id
            JOIN users u ON a.specialist_id = u.id
            JOIN study_samples ss ON ans.study_sample_id = ss.id
            JOIN samples s ON ss.sample_id = s.id
            WHERE a.study_id = ?
            ORDER BY ans.id, ann.timestamp_start_ms, ann.id
            """,
            (study_id,)
        )
        annotations_rows = await cursor.fetchall()

        # Prepare specialists CSV data
        specialists_csv = []
        for row in specialists_rows:
            specialists_csv.append({
                "specialist_id": row["specialist_id"],
                "name": row["name"],
                "email": row["email"],
                "expertise_level": row["expertise_level"] or "",
                "years_experience": row["years_experience"] or ""
            })

        # Prepare sessions CSV data
        sessions_csv = []
        audio_files = []
        for row in sessions_rows:
            # Parse image dimensions
            width = ""
            height = ""
            if row["image_dimensions_json"]:
                try:
                    dims = json.loads(row["image_dimensions_json"])
                    width = dims.get("width", "")
                    height = dims.get("height", "")
                except (json.JSONDecodeError, TypeError):
                    pass

            # Use pad_sample_id if available
            export_sample_id = row["pad_sample_id"] if row["pad_sample_id"] else row["sample_id"]

            audio_filename = ""
            if row["audio_filename"]:
                audio_filename = f"audio/{row['audio_filename']}"
                audio_files.append(row["audio_filename"])

            sessions_csv.append({
                "session_id": row["session_id"],
                "session_uuid": row["session_uuid"],
                "specialist_id": row["specialist_id"],
                "specialist_name": row["specialist_name"],
                "sample_id": export_sample_id,
                "drug_name": row["drug_name"],
                "card_id": row["card_id"],
                "status": row["status"],
                "started_at": row["started_at"] or "",
                "completed_at": row["completed_at"] or "",
                "audio_filename": audio_filename,
                "audio_duration_ms": row["audio_duration_ms"] or "",
                "image_width": width,
                "image_height": height
            })

        # Prepare annotations CSV data
        annotations_csv = []
        for row in annotations_rows:
            # Parse bbox
            bbox_x1, bbox_y1, bbox_x2, bbox_y2 = "", "", "", ""
            if row["bbox_normalized_json"]:
                try:
                    bbox = json.loads(row["bbox_normalized_json"])
                    bbox_x1 = bbox.get("x1", "")
                    bbox_y1 = bbox.get("y1", "")
                    bbox_x2 = bbox.get("x2", "")
                    bbox_y2 = bbox.get("y2", "")
                except (json.JSONDecodeError, TypeError):
                    pass

            # Parse lanes
            lanes = ""
            if row["lanes_json"]:
                try:
                    lanes_list = json.loads(row["lanes_json"])
                    lanes = ",".join(str(l) for l in lanes_list) if lanes_list else ""
                except (json.JSONDecodeError, TypeError):
                    pass

            # Keep points as JSON string for flexibility
            points_json = row["points_normalized_json"] or ""

            annotations_csv.append({
                "annotation_id": row["annotation_id"],
                "session_id": row["session_id"],
                "session_uuid": row["session_uuid"],
                "specialist_name": row["specialist_name"],
                "drug_name": row["drug_name"],
                "annotation_type": row["annotation_type"],
                "color": row["color"] or "",
                "lanes": lanes,
                "bbox_x1": bbox_x1,
                "bbox_y1": bbox_y1,
                "bbox_x2": bbox_x2,
                "bbox_y2": bbox_y2,
                "points_json": points_json,
                "timestamp_start_ms": row["timestamp_start_ms"] or "",
                "timestamp_end_ms": row["timestamp_end_ms"] or ""
            })

    # Prepare study info JSON
    study_info = {
        "id": study["id"],
        "name": study["name"],
        "description": study.get("description"),
        "instructions": study.get("instructions"),
        "eyetracking_mode": study.get("eyetracking_mode"),
        "annotation_mode": study.get("annotation_mode"),
        "default_image_width": study.get("default_image_width"),
        "default_image_height": study.get("default_image_height"),
        "created_at": study.get("created_at"),
        "exported_at": datetime.now().isoformat()
    }

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add study_info.json
        zf.writestr("study_info.json", json.dumps(study_info, indent=2))

        # Add specialists.csv
        if specialists_csv:
            csv_buffer = io.StringIO()
            fieldnames = ["specialist_id", "name", "email", "expertise_level", "years_experience"]
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(specialists_csv)
            zf.writestr("specialists.csv", csv_buffer.getvalue())

        # Add sessions.csv
        if sessions_csv:
            csv_buffer = io.StringIO()
            fieldnames = [
                "session_id", "session_uuid", "specialist_id", "specialist_name",
                "sample_id", "drug_name", "card_id", "status",
                "started_at", "completed_at", "audio_filename", "audio_duration_ms",
                "image_width", "image_height"
            ]
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sessions_csv)
            zf.writestr("sessions.csv", csv_buffer.getvalue())

        # Add annotations.csv
        if annotations_csv:
            csv_buffer = io.StringIO()
            fieldnames = [
                "annotation_id", "session_id", "session_uuid", "specialist_name",
                "drug_name", "annotation_type", "color", "lanes",
                "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2",
                "points_json", "timestamp_start_ms", "timestamp_end_ms"
            ]
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(annotations_csv)
            zf.writestr("annotations.csv", csv_buffer.getvalue())

        # Add audio files
        audio_dir = Path("data/audio")
        for audio_filename in audio_files:
            audio_path = audio_dir / audio_filename
            if audio_path.exists():
                zf.write(audio_path, f"audio/{audio_filename}")

    zip_buffer.seek(0)

    # Generate filename
    study_name_clean = "".join(c if c.isalnum() or c in "-_" else "_" for c in study["name"])
    date_str = datetime.now().strftime("%Y%m%d")
    zip_filename = f"{study_name_clean}_data_{date_str}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )
