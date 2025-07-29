# services/user_management/models/subjects.py

from sqlalchemy import Column, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.db import Base
import uuid

# Subject offered by a school
class SchoolSubject(Base):
    __tablename__ = "school_subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    name = Column(String, nullable=False)  # e.g., "Math", "Science"

    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_school_subject_name"),
    )

    school = relationship("School", backref="subjects")


# Subject mapped to a class (can be optional or compulsory)
class ClassSubject(Base):
    __tablename__ = "class_subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id = Column(UUID(as_uuid=True), ForeignKey("school_classes.id"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("school_subjects.id"), nullable=False)
    is_optional = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", name="uq_class_subject"),
    )

    school_class = relationship("SchoolClass", backref="class_subjects")
    subject = relationship("SchoolSubject")


# Optional subject mapping for student
class StudentSubject(Base):
    __tablename__ = "student_subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("school_users.id"), nullable=False)
    class_subject_id = Column(UUID(as_uuid=True), ForeignKey("class_subjects.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "class_subject_id", name="uq_student_optional_subject"),
    )

    student = relationship("SchoolUser", backref="optional_subjects")
    class_subject = relationship("ClassSubject")
