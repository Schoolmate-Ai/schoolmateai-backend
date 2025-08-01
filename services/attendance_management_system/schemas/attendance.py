from datetime import date, time
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
import uuid

class AttendanceStatus(str, Enum):
    PRESENT = "P"
    ABSENT = "A"
    HALF_DAY = "HD"
    LEAVE = "L"

class StudentAttendanceRecord(BaseModel):
    student_id: uuid.UUID
    status: AttendanceStatus = AttendanceStatus.PRESENT
    arrival_time: Optional[time] = None
    notes: Optional[str] = None

class DailyAttendanceCreate(BaseModel):
    class_id: uuid.UUID
    date: date
    records: List[StudentAttendanceRecord] = Field(
        default_factory=list,
        description="List of students with non-present status. All other students will be marked present."
    )

class AttendanceOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    status: AttendanceStatus
    arrival_time: Optional[time]
    notes: Optional[str]
    recorded_by: uuid.UUID
    recorded_by_name: str
    created_at: str

    class Config:
        from_attributes = True

class DailyAttendanceResponse(BaseModel):
    class_id: uuid.UUID
    class_name: str
    date: date
    attendances: List[AttendanceOut]