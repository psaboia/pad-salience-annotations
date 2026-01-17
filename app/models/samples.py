"""Sample models."""

from pydantic import BaseModel
from typing import Optional, List


class SampleResponse(BaseModel):
    """Response model for sample data."""
    id: int
    drug_name: str
    drug_name_display: str
    card_id: int
    filename: str
    image_path: str
    quantity: Optional[int] = None
    image_type: Optional[str] = None
    created_at: Optional[str] = None


class SampleSelectionRequest(BaseModel):
    """Request model for selecting samples for an experiment."""
    sample_ids: List[int]
