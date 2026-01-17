"""Study models."""

from pydantic import BaseModel
from typing import Optional, List


class StudyCreate(BaseModel):
    """Request model for creating a study."""
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None


class StudyUpdate(BaseModel):
    """Request model for updating a study."""
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    status: Optional[str] = None


class StudyResponse(BaseModel):
    """Response model for study data."""
    id: int
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    status: str
    created_by: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SampleInStudy(BaseModel):
    """Sample within a study context."""
    study_sample_id: int
    display_order: int
    id: int  # sample id
    drug_name: str
    drug_name_display: str
    card_id: int
    filename: str
    image_path: str


class StudyWithSamples(StudyResponse):
    """Study with its samples."""
    samples: List[SampleInStudy] = []
    sample_count: int = 0


class AssignmentCreate(BaseModel):
    """Request model for creating an assignment."""
    specialist_id: int


class AssignmentResponse(BaseModel):
    """Response model for assignment data."""
    id: int
    study_id: int
    specialist_id: int
    status: str
    randomization_seed: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None

    # Specialist profile snapshot (captured at assignment time)
    expertise_level_snapshot: Optional[str] = None
    years_experience_snapshot: Optional[int] = None
    training_date_snapshot: Optional[str] = None

    # Optional joined data
    study_name: Optional[str] = None
    study_status: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    specialist_name: Optional[str] = None
    specialist_email: Optional[str] = None


class AssignmentProgress(BaseModel):
    """Progress data for an assignment."""
    assignment_id: int
    specialist_name: str
    status: str
    started_at: Optional[str] = None
    total_samples: int
    completed_samples: int
    percentage: float
