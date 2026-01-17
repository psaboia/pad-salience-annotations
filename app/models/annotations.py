"""Annotation models."""

from pydantic import BaseModel
from typing import Optional, List, Any


class BboxNormalized(BaseModel):
    """Normalized bounding box coordinates (0-999)."""
    x1: int
    y1: int
    x2: int
    y2: int


class PointNormalized(BaseModel):
    """Normalized point coordinates (0-999)."""
    x: int
    y: int


class AnnotationData(BaseModel):
    """Individual annotation data."""
    id: Optional[int] = None
    type: str  # 'rectangle' or 'polygon'
    color: Optional[str] = None
    lanes: List[str] = []
    bbox_normalized: Optional[BboxNormalized] = None
    points_normalized: Optional[List[PointNormalized]] = None
    timestamp_start_ms: Optional[int] = None
    timestamp_end_ms: Optional[int] = None


class ImageDimensions(BaseModel):
    """Image dimension data."""
    width: int
    height: int


class AudioData(BaseModel):
    """Audio recording data."""
    format: str
    data_base64: str
    duration_ms: Optional[int] = None


class LayoutSettings(BaseModel):
    """Layout settings for reconstruction."""
    eyetracking_enabled: Optional[bool] = True
    apriltags: Optional[dict] = None
    pad_image: Optional[dict] = None
    layout: Optional[dict] = None


class AnnotationSessionCreate(BaseModel):
    """Request model for starting a new annotation session."""
    assignment_id: int
    experiment_sample_id: int


class AnnotationSessionComplete(BaseModel):
    """Request model for completing an annotation session."""
    annotations: List[AnnotationData]
    image_dimensions: ImageDimensions
    audio: Optional[AudioData] = None
    layout_settings: Optional[LayoutSettings] = None


class SampleTags(BaseModel):
    """AprilTag IDs for each corner position."""
    top_left: Optional[int] = None
    top_right: Optional[int] = None
    bottom_left: Optional[int] = None
    bottom_right: Optional[int] = None


class SampleInfo(BaseModel):
    """Sample information for session response."""
    id: int
    drug_name: str
    drug_name_display: str
    card_id: int
    filename: str
    image_path: str
    tags: Optional[SampleTags] = None


class SessionProgressResponse(BaseModel):
    """Response with current session and progress."""
    session_uuid: Optional[str] = None
    session_id: Optional[int] = None
    sample: Optional[SampleInfo] = None
    current_position: int
    total_samples: int
    completed: int
    percentage: float
    is_complete: bool = False
    next_sample: Optional[SampleInfo] = None


# Legacy models for backward compatibility
class LegacySample(BaseModel):
    """Legacy sample format from manifest.json."""
    drug_name: str
    drug_name_display: str
    card_id: int
    quantity: Optional[int] = None
    filename: str
    path: str
    image_type: Optional[str] = None


class LegacyAnnotationSession(BaseModel):
    """Legacy annotation session format (for /api/save-annotation)."""
    session_id: str
    timestamp: str
    sample: LegacySample
    image_dimensions: ImageDimensions
    annotations: List[dict]
    audio: Optional[AudioData] = None
    specialist_id: Optional[str] = None
    specialist_expertise: Optional[str] = None
    layout_settings: Optional[dict] = None
