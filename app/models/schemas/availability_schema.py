from pydantic import BaseModel
from typing import Optional
from datetime import time

class AvailabilityCreate(BaseModel):
    barbershop_id: str
    day_of_week: int
    start_time: time
    end_time: time
    is_available: Optional[bool] = True

class AvailabilityUpdate(BaseModel):
    day_of_week: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_available: Optional[bool] = None

class AvailabilityResponse(BaseModel):
    availability_id: str
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool
