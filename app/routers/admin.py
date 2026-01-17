"""Admin API router."""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List

from ..database import (
    get_db_context,
    get_all_samples,
    get_all_experiments,
    get_experiment_by_id,
    create_experiment,
    update_experiment_status,
    add_samples_to_experiment,
    get_experiment_samples,
    get_specialists,
    create_assignment,
    get_experiment_assignments,
    get_experiment_progress,
    get_all_users,
    create_user,
    update_user,
    deactivate_user,
    get_user_by_id_include_inactive,
    get_user_by_email,
)
from ..models import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    ExperimentWithSamples,
    SampleResponse,
    SampleSelectionRequest,
    AssignmentCreate,
    AssignmentResponse,
)
from ..models.auth import UserCreate, UserUpdate, UserResponse
from ..models.experiments import SampleInExperiment, AssignmentProgress
from ..services.auth import require_admin, hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Sample endpoints
@router.get("/samples", response_model=List[SampleResponse])
async def list_samples(_: dict = Depends(require_admin)):
    """Get all available samples."""
    async with get_db_context() as db:
        samples = await get_all_samples(db)
        return [SampleResponse(**s) for s in samples]


# Experiment endpoints
@router.get("/experiments", response_model=List[ExperimentResponse])
async def list_experiments(_: dict = Depends(require_admin)):
    """Get all experiments."""
    async with get_db_context() as db:
        experiments = await get_all_experiments(db)
        return [ExperimentResponse(**e) for e in experiments]


@router.post("/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_new_experiment(data: ExperimentCreate, admin: dict = Depends(require_admin)):
    """Create a new experiment."""
    async with get_db_context() as db:
        exp_id = await create_experiment(
            db,
            name=data.name,
            description=data.description,
            instructions=data.instructions,
            created_by=admin["id"]
        )
        experiment = await get_experiment_by_id(db, exp_id)
        return ExperimentResponse(**experiment)


@router.get("/experiments/{experiment_id}", response_model=ExperimentWithSamples)
async def get_experiment(experiment_id: int, _: dict = Depends(require_admin)):
    """Get a specific experiment with its samples."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        samples = await get_experiment_samples(db, experiment_id)
        sample_models = [SampleInExperiment(**s) for s in samples]

        return ExperimentWithSamples(
            **experiment,
            samples=sample_models,
            sample_count=len(sample_models)
        )


@router.put("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(experiment_id: int, data: ExperimentUpdate, _: dict = Depends(require_admin)):
    """Update an experiment."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        # Update fields
        if data.name is not None:
            await db.execute(
                "UPDATE experiments SET name = ?, updated_at = datetime('now') WHERE id = ?",
                (data.name, experiment_id)
            )
        if data.description is not None:
            await db.execute(
                "UPDATE experiments SET description = ?, updated_at = datetime('now') WHERE id = ?",
                (data.description, experiment_id)
            )
        if data.instructions is not None:
            await db.execute(
                "UPDATE experiments SET instructions = ?, updated_at = datetime('now') WHERE id = ?",
                (data.instructions, experiment_id)
            )
        if data.status is not None:
            await update_experiment_status(db, experiment_id, data.status)
        else:
            await db.commit()

        experiment = await get_experiment_by_id(db, experiment_id)
        return ExperimentResponse(**experiment)


@router.delete("/experiments/{experiment_id}")
async def delete_experiment(experiment_id: int, _: dict = Depends(require_admin)):
    """Delete an experiment (only if draft)."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        if experiment["status"] not in ("draft", "archived"):
            raise HTTPException(
                status_code=400,
                detail="Can only delete draft or archived experiments"
            )

        await db.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        await db.commit()

        return {"status": "success", "message": "Experiment deleted"}


@router.post("/experiments/{experiment_id}/activate")
async def activate_experiment(experiment_id: int, _: dict = Depends(require_admin)):
    """Activate an experiment (move from draft to active)."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        if experiment["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Can only activate draft experiments"
            )

        # Check that experiment has samples
        samples = await get_experiment_samples(db, experiment_id)
        if not samples:
            raise HTTPException(
                status_code=400,
                detail="Cannot activate experiment without samples"
            )

        # Check that experiment has assignments
        assignments = await get_experiment_assignments(db, experiment_id)
        if not assignments:
            raise HTTPException(
                status_code=400,
                detail="Cannot activate experiment without specialist assignments"
            )

        await update_experiment_status(db, experiment_id, "active")

        return {"status": "success", "message": "Experiment activated"}


@router.post("/experiments/{experiment_id}/pause")
async def pause_experiment(experiment_id: int, _: dict = Depends(require_admin)):
    """Pause an active experiment."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        if experiment["status"] != "active":
            raise HTTPException(
                status_code=400,
                detail="Can only pause active experiments"
            )

        await update_experiment_status(db, experiment_id, "paused")

        return {"status": "success", "message": "Experiment paused"}


@router.post("/experiments/{experiment_id}/resume")
async def resume_experiment(experiment_id: int, _: dict = Depends(require_admin)):
    """Resume a paused experiment."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        if experiment["status"] != "paused":
            raise HTTPException(
                status_code=400,
                detail="Can only resume paused experiments"
            )

        await update_experiment_status(db, experiment_id, "active")

        return {"status": "success", "message": "Experiment resumed"}


# Sample management for experiments
@router.get("/experiments/{experiment_id}/samples", response_model=List[SampleInExperiment])
async def get_experiment_sample_list(experiment_id: int, _: dict = Depends(require_admin)):
    """Get samples assigned to an experiment."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        samples = await get_experiment_samples(db, experiment_id)
        return [SampleInExperiment(**s) for s in samples]


@router.post("/experiments/{experiment_id}/samples")
async def set_experiment_samples(
    experiment_id: int,
    data: SampleSelectionRequest,
    _: dict = Depends(require_admin)
):
    """Set the samples for an experiment (replaces existing)."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        if experiment["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Can only modify samples for draft experiments"
            )

        # Clear existing samples
        await db.execute(
            "DELETE FROM experiment_samples WHERE experiment_id = ?",
            (experiment_id,)
        )
        await db.commit()

        # Add new samples
        await add_samples_to_experiment(db, experiment_id, data.sample_ids)

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
        return [
            UserResponse(
                id=u["id"],
                email=u["email"],
                name=u["name"],
                role=u["role"],
                expertise_level=u.get("expertise_level"),
                years_experience=u.get("years_experience"),
                training_date=u.get("training_date"),
                institution=u.get("institution"),
                specializations=u.get("specializations"),
                is_active=bool(u["is_active"]),
                created_at=u.get("created_at")
            )
            for u in users
        ]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(data: UserCreate, _: dict = Depends(require_admin)):
    """Create a new user."""
    async with get_db_context() as db:
        # Check if email already exists
        existing = await get_user_by_email(db, data.email)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )

        password_hash = hash_password(data.password)

        user_id = await create_user(
            db,
            email=data.email,
            name=data.name,
            password_hash=password_hash,
            role=data.role,
            expertise_level=data.expertise_level,
            years_experience=data.years_experience,
            training_date=data.training_date,
            institution=data.institution,
            specializations=data.specializations
        )

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
async def update_existing_user(user_id: int, data: UserUpdate, _: dict = Depends(require_admin)):
    """Update a user."""
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

        await update_user(
            db,
            user_id=user_id,
            email=data.email,
            name=data.name,
            password_hash=password_hash,
            role=data.role,
            expertise_level=data.expertise_level,
            years_experience=data.years_experience,
            training_date=data.training_date,
            institution=data.institution,
            specializations=data.specializations,
            is_active=data.is_active
        )

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


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """Deactivate a user (soft delete)."""
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate your own account"
        )

    async with get_db_context() as db:
        user = await get_user_by_id_include_inactive(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await deactivate_user(db, user_id)

        return {"status": "success", "message": "User deactivated"}


# Assignment management
@router.get("/experiments/{experiment_id}/assignments", response_model=List[AssignmentResponse])
async def get_assignments(experiment_id: int, _: dict = Depends(require_admin)):
    """Get all assignments for an experiment."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        assignments = await get_experiment_assignments(db, experiment_id)
        return [AssignmentResponse(**a) for a in assignments]


@router.post("/experiments/{experiment_id}/assignments", response_model=AssignmentResponse)
async def create_new_assignment(
    experiment_id: int,
    data: AssignmentCreate,
    _: dict = Depends(require_admin)
):
    """Assign a specialist to an experiment."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        if experiment["status"] not in ("draft", "active"):
            raise HTTPException(
                status_code=400,
                detail="Cannot add assignments to this experiment"
            )

        # Fetch specialist profile for snapshot
        specialist = await get_user_by_id_include_inactive(db, data.specialist_id)
        if not specialist:
            raise HTTPException(status_code=404, detail="Specialist not found")

        try:
            assignment_id = await create_assignment(
                db,
                experiment_id,
                data.specialist_id,
                expertise_level_snapshot=specialist.get("expertise_level"),
                years_experience_snapshot=specialist.get("years_experience"),
                training_date_snapshot=specialist.get("training_date")
            )
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                raise HTTPException(
                    status_code=400,
                    detail="Specialist already assigned to this experiment"
                )
            raise

        assignments = await get_experiment_assignments(db, experiment_id)
        assignment = next((a for a in assignments if a["id"] == assignment_id), None)

        return AssignmentResponse(**assignment)


@router.delete("/experiments/{experiment_id}/assignments/{specialist_id}")
async def delete_assignment(
    experiment_id: int,
    specialist_id: int,
    _: dict = Depends(require_admin)
):
    """Remove a specialist from an experiment."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        if experiment["status"] not in ("draft",):
            raise HTTPException(
                status_code=400,
                detail="Can only remove assignments from draft experiments"
            )

        await db.execute(
            "DELETE FROM assignments WHERE experiment_id = ? AND specialist_id = ?",
            (experiment_id, specialist_id)
        )
        await db.commit()

        return {"status": "success", "message": "Assignment removed"}


# Progress tracking
@router.get("/experiments/{experiment_id}/progress")
async def get_progress(experiment_id: int, _: dict = Depends(require_admin)):
    """Get detailed progress for an experiment."""
    async with get_db_context() as db:
        experiment = await get_experiment_by_id(db, experiment_id)
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        progress = await get_experiment_progress(db, experiment_id)
        progress["experiment"] = ExperimentResponse(**experiment).model_dump()

        return progress
