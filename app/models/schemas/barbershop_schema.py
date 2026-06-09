from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class BarbershopCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class BarbershopUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class BarbershopResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    invite_code: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class MemberCreate(BaseModel):
    user_id: str
    role: str

class MemberUpdate(BaseModel):
    status: Optional[str] = None
    role: Optional[str] = None

class MemberResponse(BaseModel):
    member_id: str
    user_id: str
    name: Optional[str] = None
    role: str
    status: str
    joined_at: Optional[datetime] = None
