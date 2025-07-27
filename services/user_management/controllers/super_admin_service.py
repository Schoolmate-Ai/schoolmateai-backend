# services/user_management/controllers/super_admin_service.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext
from uuid import uuid4

from services.user_management.models.super_admin import SuperAdmin
from services.user_management.models.schools import School
from services.user_management.schemas.super_admin import (
    SuperAdminCreate,
    SuperAdminOut,
    SuperAdminLogin,
    SuperAdminLoginResponse
)
from services.user_management.schemas.schools import (
    SchoolCreate,
    SchoolOut
)

from shared.db import get_db
from shared.auth import verify_password, create_access_token, get_current_super_admin_user

router = APIRouter(prefix="/superadmins", tags=["SuperAdmin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- SUPER ADMIN REGISTRATION ---
@router.post("/", response_model=SuperAdminOut)
async def register_super_admin(payload: SuperAdminCreate, db: AsyncSession = Depends(get_db)):
    hashed_pw = pwd_context.hash(payload.password)
    new_admin = SuperAdmin(
        name=payload.name,
        email=payload.email,
        hashed_password=hashed_pw
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    return new_admin


# --- SUPER ADMIN LOGIN ---
@router.post("/login", response_model=SuperAdminLoginResponse)
async def login_superadmin(payload: SuperAdminLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SuperAdmin).where(SuperAdmin.email == payload.email))
    super_admin = result.scalars().first()

    if not super_admin or not verify_password(payload.password, super_admin.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token({"sub": super_admin.email, "role": super_admin.role})

    return SuperAdminLoginResponse(
        name=super_admin.name,
        email=super_admin.email,
        role=super_admin.role,
        access_token=access_token
    )

# --- SCHOOL REGISTRATION ---
@router.post("/register-school", response_model=SchoolOut)
async def register_school(
    school_data: SchoolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_super_admin_user)
):
    """
    Register a new school (only accessible by superadmin)
    """
    from uuid import uuid4  # Add this import at the top of your file
    
    # Check if school with same email already exists
    if school_data.email:
        result = await db.execute(select(School).where(School.email == school_data.email))
        existing_school = result.scalars().first()
        
        if existing_school:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="School with this email already exists"
            )
    
    # Check unique constraint on name+address
    result = await db.execute(
        select(School).where(
            (School.name == school_data.name) & 
            (School.address == school_data.address)
        )
    )
    existing_school = result.scalars().first()
    
    if existing_school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School with this name and address already exists"
        )
    
    # Create new school with generated UUID
    new_school = School(
        id=str(uuid4()),  # Generate UUID and convert to string
        name=school_data.name,
        email=school_data.email,
        address=school_data.address,
        phone=school_data.phone,
        board=school_data.board
    )
    
    db.add(new_school)
    await db.commit()
    await db.refresh(new_school)
    
    return new_school