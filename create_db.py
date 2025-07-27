# create_db.py
import asyncio
from shared.db import engine, Base

# Import all models here so they are registered with SQLAlchemy's metadata

from services.user_management.models.super_admin import SuperAdmin
from services.user_management.models.schools import School
from services.user_management.models.users import SchoolUser

async def init_models():
    async with engine.begin() as conn:
        print("🔧 Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables created.")

if __name__ == "__main__":
    asyncio.run(init_models())
