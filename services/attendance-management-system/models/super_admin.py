# services/user_management/models/super_admin.py
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from shared.db import Base

class SuperAdmin(Base):
    __tablename__ = "superadmins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="superadmin")
    created_at = Column(DateTime, default=datetime.utcnow)
