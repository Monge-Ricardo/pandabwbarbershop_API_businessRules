from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProductCreate(BaseModel):
    barbershop_id: str
    name: str
    description: Optional[str] = None
    price: float = 0.0
    stock: int = 0
    image_url: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None

class ProductResponse(BaseModel):
    product_id: str
    name: str
    stock: int
    price: float
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    barbershop_id: Optional[str] = None
