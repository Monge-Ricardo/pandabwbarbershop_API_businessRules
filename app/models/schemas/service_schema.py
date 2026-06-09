from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ServiceCreate(BaseModel):
    barbershop_id: str
    name: str
    description: Optional[str] = None
    price: float
    duration_minutes: int

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None

class ServiceResponse(BaseModel):
    service_id: str
    name: str
    price: float
    is_active: bool
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    barbershop_id: Optional[str] = None
