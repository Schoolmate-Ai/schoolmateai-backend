# create_db.py
import asyncio
from shared.db import engine, Base

# Import all models here so they are registered with SQLAlchemy's metadata

# from services.user_management.models.super_admin import SuperAdmin
# from services.user_management.models.schools import School
# from services.user_management.models.users import SchoolUser
# from services.user_management.models.classes import SchoolClass
# from services.user_management.models.subjects import StudentSubject, ClassSubject, SchoolSubject
# from services.user_management.models.teachers import TeacherSubject, ClassTeacher
import services.user_management.models
import services.attendance_management_system.models

async def init_models():
    async with engine.begin() as conn:
        print("🔧 Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables created.")

if __name__ == "__main__":
    asyncio.run(init_models())
