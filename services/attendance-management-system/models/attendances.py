# services/attendance-management.py
from sqlalchemy import Column, ForeignKey, Date, Time, Enum, Text, String, Index, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from shared.db import Base
import enum
import uuid
from datetime import datetime

class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    HALF_DAY = "half_day"

class Attendance(Base):
    __tablename__ = "attendances"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("school_classes.id"), nullable=False)
    date = Column(Date, nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("school_users.id"), nullable=False)
    status = Column(Enum(AttendanceStatus), nullable=False)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("school_users.id"), nullable=False)
    arrival_time = Column(Time)  # Only for late arrivals
    notes = Column(Text)
    metadata = Column(JSONB)  # For extended data
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    school = relationship("School")
    class_ = relationship("SchoolClass")
    student = relationship("SchoolUser", foreign_keys=[student_id])
    recorder = relationship("SchoolUser", foreign_keys=[recorded_by])
    
    __table_args__ = (
        Index('idx_attendance_school_date', 'school_id', 'date'),
        Index('idx_attendance_class_date', 'class_id', 'date'),
        Index('idx_attendance_student_date', 'student_id', 'date'),
        UniqueConstraint('class_id', 'date', 'student_id', name='uq_attendance_per_student_per_day'),
    )