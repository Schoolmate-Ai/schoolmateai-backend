# services/user_management/schemas/subjects.py

from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class SchoolSubjectCreate(BaseModel):
    school_id: str
    name: str

class SchoolSubjectOut(BaseModel):
    id: UUID
    name: str

    class Config:
        orm_mode = True


class ClassSubjectCreate(BaseModel):
    class_id: UUID
    subject_id: UUID
    teacher_id: Optional[UUID] = None
    is_optional: bool = False

class ClassSubjectOut(BaseModel):
    id: UUID
    class_id: UUID
    subject_id: UUID
    teacher_id: Optional[UUID] = None
    is_optional: bool

    class Config:
        orm_mode = True


class StudentSubjectCreate(BaseModel):
    student_id: UUID
    class_subject_id: UUID

class StudentSubjectOut(BaseModel):
    id: UUID
    class_subject_id: UUID

    class Config:
        orm_mode = True

class SubjectMappingInput(BaseModel):
    subject_id: UUID
    is_optional: bool = False

class ClassSubjectDetailOut(BaseModel):
    id: UUID
    subject_id: UUID
    subject_name: str
    is_optional: bool
    teacher_id: Optional[UUID] = None
    teacher_name: Optional[str] = None

    class Config:
        orm_mode = True

class StudentSubjectDetailOut(BaseModel):
    subject_id: UUID
    subject_name: str
    is_optional: bool

    class Config:
        orm_mode = True


class AssignTeacherToSubject(BaseModel):
    teacher_id: UUID
    class_subject_id: UUID