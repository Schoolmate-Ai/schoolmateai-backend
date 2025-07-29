from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID

class SchoolUserRole(str, Enum):
    SCHOOL_SUPERADMIN = "school_superadmin"
    SCHOOL_ADMIN = "school_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"

class SchoolUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    class_id: Optional[UUID] = None
    role: SchoolUserRole
    school_id: str  # UUID as string
    profile_data: Optional[Dict[str, Any]] = None

class SchoolUserOut(BaseModel):
    id: UUID 
    name: str
    email: EmailStr
    role: SchoolUserRole
    school_id: str
    class_id: Optional[UUID]
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True

class SchoolUserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    role: Optional[SchoolUserRole]
    profile_data: Optional[Dict[str, Any]]

class SchoolUserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class SchoolUserLoginResponse(BaseModel):
    name: str
    school_id: str
    access_token: str

class ClassStudentRequest(BaseModel):
    school_id: str
    class_id: UUID
    
class StudentOut(BaseModel):
    id: UUID
    name: str
    email: str
    class_id: UUID
    school_id: str

    class Config:
        orm_mode = True
