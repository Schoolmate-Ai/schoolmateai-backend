from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime

class SuperAdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "superadmin"  

class SuperAdminOut(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str                  
    created_at: datetime

    class Config:
        orm_mode = True


class SuperAdminLogin(BaseModel):
    email: EmailStr
    password: str

class SuperAdminLoginResponse(BaseModel):
    name: str
    email: EmailStr
    role: str
    access_token: str
