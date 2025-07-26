# services/user_management/api/super_admin_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from services.user_management.schemas.super_admin import SuperAdminCreate, SuperAdminOut, SuperAdminLogin, SuperAdminLoginResponse
from services.user_management.controllers.super_admin_service import create_super_admin, login_super_admin
from shared.db import get_db

router = APIRouter(prefix="/superadmins", tags=["SuperAdmin"])

@router.post("/", response_model=SuperAdminOut)
async def register_super_admin(payload: SuperAdminCreate, db: AsyncSession = Depends(get_db)):
    return await create_super_admin(payload, db)

@router.post("/login", response_model=SuperAdminLoginResponse)
async def login_superadmin(payload: SuperAdminLogin, db: AsyncSession = Depends(get_db)):
    return await login_super_admin(payload, db)