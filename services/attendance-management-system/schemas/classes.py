# services/user_management/schemas/classes.py

from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class SchoolClassCreate(BaseModel):
    school_id: str
    class_name: str
    section: str

class SchoolClassOut(BaseModel):
    id: UUID
    class_name: str
    section: str

    class Config:
        orm_mode = True
