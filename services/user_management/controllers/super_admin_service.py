# services/user_management/services/super_admin_service.py
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from services.user_management.models.super_admin import SuperAdmin
from services.user_management.schemas.super_admin import SuperAdminCreate, SuperAdminLogin, SuperAdminLoginResponse
from fastapi import HTTPException, status
from shared.auth import verify_password, create_access_token

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_super_admin(data: SuperAdminCreate, db: AsyncSession):
    hashed_pw = pwd_context.hash(data.password)
    new_admin = SuperAdmin(
        name=data.name,
        email=data.email,
        hashed_password=hashed_pw
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    return new_admin

async def login_super_admin(data: SuperAdminLogin, db: AsyncSession) -> SuperAdminLoginResponse:
    try:
        result = await db.execute(select(SuperAdmin).where(SuperAdmin.email == data.email))
        super_admin = result.scalars().first()

        if not super_admin or not verify_password(data.password, super_admin.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        access_token = create_access_token({"sub": super_admin.email, "role": super_admin.role})

        return SuperAdminLoginResponse(
            name=super_admin.name,
            email=super_admin.email,
            role=super_admin.role,
            access_token=access_token
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")