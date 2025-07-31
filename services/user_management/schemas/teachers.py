# services/user_management/schemas/teachers.py

from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime


# Request schema to assign a class teacher
class ClassTeacherCreate(BaseModel):
    teacher_id: UUID4
    class_id: UUID4


# Response schema
class ClassTeacherOut(BaseModel):
    id: UUID4
    teacher_id: UUID4
    class_id: UUID4

    class Config:
        orm_mode = True


# Request schema to assign teacher to a class_subject
class TeacherSubjectCreate(BaseModel):
    teacher_id: UUID4
    class_subject_id: UUID4


# Response schema
class TeacherSubjectOut(BaseModel):
    id: UUID4
    teacher_id: UUID4
    class_subject_id: UUID4

    class Config:
        orm_mode = True

        
class TeacherSubjectDetailedOut(BaseModel):
    id: UUID4
    teacher_id: UUID4
    class_subject_id: UUID4
    subject_name: str
    class_name: str
    section: str

    class Config:
        orm_mode = True


class ClassWithTeacherResponse(BaseModel):
    class_id: UUID4
    class_name: str
    section: Optional[str] = None
    teacher_id: Optional[UUID4] = None
    teacher_name: Optional[str] = "No teacher assigned"

    class Config:
        orm_mode = True

class TeacherSubjectAssignmentOut(BaseModel):
    class_id: UUID4
    class_display_name: str
    subject_id: UUID4
    subject_name: str
    is_optional: bool

    class Config:
        orm_mode = True