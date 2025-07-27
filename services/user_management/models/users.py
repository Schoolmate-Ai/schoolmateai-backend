# services/user_management/models/user.py
from sqlalchemy import Column, String, Enum, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
from shared.db import Base
import enum
import uuid

class SchoolUserRole(str, enum.Enum):
    SCHOOL_SUPERADMIN = "school_superadmin"
    SCHOOL_ADMIN = "school_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"

class SchoolUser(Base):
    __tablename__ = "school_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(SchoolUserRole), nullable=False)
    school_id = Column(String, ForeignKey('schools.id'), nullable=False)  # Changed to match School.id type
    profile_data = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to school
    school = relationship("School", back_populates="users")

    __table_args__ = (
        Index('idx_school_user_email', 'email'),
        Index('idx_school_user_role', 'role'),
        Index('idx_school_user_school', 'school_id'),
    )