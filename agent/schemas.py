from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ApplicationRecord(BaseModel):
    """Structured record used by the job agent to persist one application result."""

    company: str
    role: str
    match_score: int = Field(ge=0, le=100)
    status: str
    resume_version: str
    cover_letter: str
    # We generate the timestamp inside the model so every saved record has a uniform shape.
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
