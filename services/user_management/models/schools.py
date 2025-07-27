# services/user_management/models/schools.py

from sqlalchemy import Column, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from shared.db import Base  

class School(Base):
    __tablename__ = "schools"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    board = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('name', 'address', name='uq_school_name_address'),
    )
