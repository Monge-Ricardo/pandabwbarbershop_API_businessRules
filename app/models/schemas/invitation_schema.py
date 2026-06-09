from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InvitationCreate(BaseModel):
    expires_at: Optional[datetime] = None

class InvitationResponse(BaseModel):
    invitation_id: str
    code: str
    expires_at: Optional[datetime] = None
    is_active: bool
