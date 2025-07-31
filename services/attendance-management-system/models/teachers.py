# services/user_management/models/teachers.py

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.db import Base
import uuid

class ClassTeacher(Base):
    __tablename__ = "class_teachers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("school_users.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("school_classes.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("teacher_id", name="uq_class_teacher_one_class"),
        UniqueConstraint("class_id", name="uq_class_teacher_per_class"),
    )

    teacher = relationship("SchoolUser", back_populates="class_teacher_of")
    class_ = relationship("SchoolClass", back_populates="class_teacher")

class TeacherSubject(Base):
    __tablename__ = "teacher_subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("school_users.id"), nullable=False)
    class_subject_id = Column(UUID(as_uuid=True), ForeignKey("class_subjects.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("teacher_id", "class_subject_id", name="uq_teacher_class_subject"),
    )

    teacher = relationship("SchoolUser", back_populates="subjects_taught")
    class_subject = relationship("ClassSubject", back_populates="teachers")

