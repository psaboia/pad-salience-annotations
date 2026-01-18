"""Admin API router."""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List

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
            created_by=admin["id"]
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
                s.card_id
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
                u.id as specialist_id,
                u.name as specialist_name,
                u.email as specialist_email,
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
                "image_path": session['image_path']
            },
            "study": {
                "id": session['study_id'],
                "name": session['study_name']
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
                s.completed_at,
                u.name as specialist_name,
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
                "completed_at": row["completed_at"],
                "specialist_name": row["specialist_name"],
                "study_name": row["study_name"]
            }
            for row in rows
        ]
