from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from services.user_management.models.users import SchoolUser, SchoolUserRole
from services.user_management.schemas.users import (
    SchoolUserLoginRequest,
    SchoolUserLoginResponse,
    SchoolUserCreate,
    SchoolUserOut,
    StudentOut,
    ClassStudentRequest
)
from shared.auth import verify_password, create_access_token
from shared.db import get_db
from sqlalchemy.exc import IntegrityError
from shared.auth import get_current_user
from passlib.context import CryptContext
from fastapi import Body
from services.user_management.models.classes import SchoolClass
from services.user_management.schemas.classes import SchoolClassCreate, SchoolClassOut
from typing import List
from uuid import UUID


router = APIRouter(prefix="/school", tags=["SchoolUser"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- SCHOOL UNIVERAL USER LOGIN ---
@router.post("/login", response_model=SchoolUserLoginResponse)
async def school_user_login(
    payload: SchoolUserLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SchoolUser).where(SchoolUser.email == payload.email)
    )
    user = result.scalars().first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Include user_id, role, email in token
    token_data = {
        "sub": user.email,
        "role": user.role,
        "user_id": str(user.id)
    }

    access_token = create_access_token(token_data)

    return SchoolUserLoginResponse(
        name=user.name,
        school_id=user.school_id,
        access_token=access_token
    )

# --- SCHOOL UNIVERAL USER LOGIN ---
@router.post("/register-admin", response_model=SchoolUserOut)
async def register_school_admin(
    payload: SchoolUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # ✅ Only school_superadmin can create school_admins
    if current_user["role"] != SchoolUserRole.SCHOOL_SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school_superadmin can create school_admin users"
        )

    # 🔒 Prevent creating other roles (enforced here)
    if payload.role != SchoolUserRole.SCHOOL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only 'school_admin' role can be created via this route"
        )

    # 🧠 Ensure school_id matches token's user school (multi-tenant safety)
    result = await db.execute(
        select(SchoolUser).where(SchoolUser.id == current_user["user_id"])
    )
    creator = result.scalars().first()

    if not creator or creator.school_id != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create admins for your own school"
        )

    # 🚫 Check if email exists
    result = await db.execute(select(SchoolUser).where(SchoolUser.email == payload.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists"
        )

    hashed_pw = pwd_context.hash(payload.password)

    new_user = SchoolUser(
        name=payload.name,
        email=payload.email,
        hashed_password=hashed_pw,
        role=payload.role,
        school_id=payload.school_id,
        profile_data=payload.profile_data
    )

    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity error while creating user")
    
    await db.refresh(new_user)
    return new_user

# --- REGISTER TEACHER ---
@router.post("/register-teacher", response_model=SchoolUserOut)
async def register_teacher(
    payload: SchoolUserCreate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school_admin or school_superadmin can create teacher accounts"
        )

    # Ensure role is 'teacher' only
    if payload.role != SchoolUserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This route can only be used to register teachers"
        )

    # Ensure user creates teacher for their own school
    result = await db.execute(select(SchoolUser).where(SchoolUser.id == current_user["user_id"]))
    creator = result.scalars().first()
    if not creator or creator.school_id != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create teachers for your own school"
        )

    existing_user = await db.execute(select(SchoolUser).where(SchoolUser.email == payload.email))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    hashed_pw = pwd_context.hash(payload.password)

    new_teacher = SchoolUser(
        name=payload.name,
        email=payload.email,
        hashed_password=hashed_pw,
        role=SchoolUserRole.TEACHER,
        school_id=payload.school_id,
        profile_data=payload.profile_data
    )

    db.add(new_teacher)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity error while creating teacher")
    
    await db.refresh(new_teacher)
    return new_teacher

# --- REGISTER STUDENT ---
@router.post("/register-student", response_model=SchoolUserOut)
async def register_student(
    payload: SchoolUserCreate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school_admin or school_superadmin can create student accounts"
        )

    if payload.role != SchoolUserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This route can only be used to register students"
        )

    result = await db.execute(select(SchoolUser).where(SchoolUser.id == current_user["user_id"]))
    creator = result.scalars().first()
    if not creator or creator.school_id != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create students for your own school"
        )

    existing_user = await db.execute(select(SchoolUser).where(SchoolUser.email == payload.email))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    hashed_pw = pwd_context.hash(payload.password)

    new_student = SchoolUser(
        name=payload.name,
        email=payload.email,
        hashed_password=hashed_pw,
        role=SchoolUserRole.STUDENT,
        school_id=payload.school_id,
        class_id = payload.class_id,
        profile_data=payload.profile_data
    )

    db.add(new_student)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity error while creating student")
    
    await db.refresh(new_student)
    return new_student

# --- ADD CLASS ---
@router.post("/add-class", response_model=SchoolClassOut)
async def add_class(
    payload: SchoolClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school_admin or school_superadmin can add classes"
        )

    # Check if the user is adding to their own school
    result = await db.execute(select(SchoolUser).where(SchoolUser.id == current_user["user_id"]))
    user = result.scalars().first()
    if not user or user.school_id != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add classes to your own school"
        )

    # Check if the class already exists
    existing_class_query = await db.execute(
        select(SchoolClass).where(
            SchoolClass.school_id == payload.school_id,
            SchoolClass.class_name == payload.class_name,
            SchoolClass.section == payload.section
        )
    )
    if existing_class_query.scalars().first():
        raise HTTPException(status_code=409, detail="Class with same name and section already exists")

    new_class = SchoolClass(
        school_id=payload.school_id,
        class_name=payload.class_name,
        section=payload.section
    )

    db.add(new_class)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Integrity error while creating class")

    await db.refresh(new_class)
    return new_class

# --- GET CLASSES BY SCHOOL ID ---
@router.get("/{school_id}/classes", response_model=list[SchoolClassOut])
async def get_all_classes_with_sections(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    stmt = select(SchoolClass).where(SchoolClass.school_id == school_id)
    result = await db.execute(stmt)
    all_classes = result.scalars().all()
    return all_classes

# --- GET CLASS SECTIONS BY SCHOOL ID AND CLASSNAME ---
#  /school/school-123/class-sections?class_name=1st
@router.get("/{school_id}/class-sections", response_model=list[str])
async def get_sections_for_class_name(
    school_id: str,
    class_name: str = Query(..., description="Class name like '1st' or '2nd'"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    stmt = select(SchoolClass.section).where(
        SchoolClass.school_id == school_id,
        SchoolClass.class_name == class_name
    )
    result = await db.execute(stmt)
    sections = result.scalars().all()
    return sections

# --- GET STUDENTS BY SCHOOL ID AND CLASS ID ---
@router.post("/by_class", response_model=List[StudentOut])
async def get_students_by_class(
    payload: ClassStudentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in [
        SchoolUserRole.TEACHER,
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access students"
        )

    result = await db.execute(
        select(SchoolUser).where(
            SchoolUser.school_id == payload.school_id,
            SchoolUser.class_id == payload.class_id,
            SchoolUser.role == SchoolUserRole.STUDENT
        )
    )
    students = result.scalars().all()
    return students