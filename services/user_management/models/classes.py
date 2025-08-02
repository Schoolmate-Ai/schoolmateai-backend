# services/user_management/models/classes.py
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.db import Base
import uuid

class SchoolClass(Base):
    __tablename__ = "school_classes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    class_name = Column(String, nullable=False)   # E.g., "1st", "2nd", "Nursery"
    section = Column(String, nullable=False)      # E.g., "A", "B"

    __table_args__ = (
        UniqueConstraint("school_id", "class_name", "section", name="uq_school_class_section"),
        Index("ix_school_class_school_id", "school_id"),
        Index("ix_school_class_school_class", "school_id", "class_name"),
    )

    school = relationship("School", back_populates="classes")
    students = relationship("SchoolUser", back_populates="student_class", cascade="all, delete-orphan")
    class_subjects = relationship("ClassSubject", back_populates="school_class", cascade="all, delete-orphan")
    class_teacher = relationship("ClassTeacher", back_populates="class_", uselist=False, cascade="all, delete-orphan")

