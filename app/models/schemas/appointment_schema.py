from pydantic import BaseModel
from typing import Optional, List
from datetime import date, time, datetime

class AppointmentCreate(BaseModel):
    barber_id: str
    client_id: str
    barbershop_id: str
    appointment_date: date
    start_time: time
    end_time: time
    notes: Optional[str] = None
    service_id: Optional[str] = None  # Option to bind service immediately

class AppointmentUpdate(BaseModel):
    appointment_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    appointment_id: str
    barber_id: str
    client_id: str
    appointment_date: date
    status: str
    notes: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    barbershop_id: Optional[str] = None

class AppointmentServiceBind(BaseModel):
    service_id: str
