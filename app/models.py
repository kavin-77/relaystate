from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ReviewClaimRequest(BaseModel):
    approved: Optional[bool] = None
    rejected: Optional[bool] = None
    summary: Optional[str] = None
    manual_notes: Optional[str] = None

class ManualRedactRequest(BaseModel):
    target_string: str
    replacement: Optional[str] = "[MANUALLY_REDACTED]"

class SignoffRequest(BaseModel):
    notes: Optional[str] = "Formal digital sign-off completed."
