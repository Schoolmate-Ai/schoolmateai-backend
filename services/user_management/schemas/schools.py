# services/user_management/schemas/schools.py

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class SchoolCreate(BaseModel):
    name: str
    address: str
    board: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class SchoolOut(BaseModel):
    id: str
    name: str
    address: str
    board: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
