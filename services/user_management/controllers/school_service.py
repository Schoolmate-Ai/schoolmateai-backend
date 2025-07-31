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
    ClassStudentRequest,
    SchoolTeacherOut
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
from services.user_management.models.subjects import SchoolSubject
from services.user_management.schemas.subjects import SchoolSubjectCreate, SchoolSubjectOut


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
        "user_id": str(user.id),
        "school_id": user.school_id
    }

    access_token = create_access_token(token_data)

    return SchoolUserLoginResponse(
        name=user.name,
        school_id=user.school_id,
        access_token=access_token
    )


# --- SCHOOL ADMIN REGISTRATION ---
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

    # 🧠 Ensure school_id matches token's user school (from token)
    if current_user["school_id"] != payload.school_id:
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
    # Role validation
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school_admin or school_superadmin can create teacher accounts"
        )

    # Ensure only teacher role can be created via this endpoint
    if payload.role != SchoolUserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This route can only be used to register teachers"
        )

    # School ownership verification (from token)
    if current_user["school_id"] != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create teachers for your own school"
        )

    # Check for existing email
    existing_user = await db.execute(
        select(SchoolUser).where(SchoolUser.email == payload.email)
    )
    if existing_user.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Create new teacher
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity error while creating teacher"
        )
    
    await db.refresh(new_teacher)
    return new_teacher


# --- REGISTER STUDENT ---
@router.post("/register-student", response_model=SchoolUserOut)
async def register_student(
    payload: SchoolUserCreate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Authorization check
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school administrators can create student accounts"
        )

    # Role validation
    if payload.role != SchoolUserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only for student registration"
        )

    # School ownership verification (from token)
    if current_user["school_id"] != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create students for your own school"
        )

    # Check for existing email
    existing_user = await db.execute(
        select(SchoolUser).where(SchoolUser.email == payload.email)
    )
    if existing_user.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create student
    new_student = SchoolUser(
        name=payload.name,
        email=payload.email,
        hashed_password=pwd_context.hash(payload.password),
        role=SchoolUserRole.STUDENT,
        school_id=payload.school_id,
        class_id=payload.class_id,
        profile_data=payload.profile_data
    )

    db.add(new_student)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )
    
    await db.refresh(new_student)
    return new_student


# --- ADD CLASS ---
@router.post("/add-class", response_model=SchoolClassOut)
async def add_class(
    payload: SchoolClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Authorization check
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to add classes"
        )

    # School ownership verification (from token)
    if current_user["school_id"] != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add classes to your own school"
        )

    # Check for existing class
    existing_class = await db.execute(
        select(SchoolClass).where(
            SchoolClass.school_id == payload.school_id,
            SchoolClass.class_name == payload.class_name,
            SchoolClass.section == payload.section
        )
    )
    if existing_class.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Class with this name and section already exists"
        )

    # Create new class
    new_class = SchoolClass(
        school_id=payload.school_id,
        class_name=payload.class_name,
        section=payload.section
    )

    db.add(new_class)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )

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
    # Verify the requested school matches the user's school
    if current_user["school_id"] != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only access sections from your own school"
        )

    # Get sections for the specified class
    sections = await db.execute(
        select(SchoolClass.section).where(
            SchoolClass.school_id == school_id,
            SchoolClass.class_name == class_name
        )
    )
    return sections.scalars().all()


# --- GET STUDENTS BY SCHOOL ID AND CLASS ID ---
@router.post("/students/by_class", response_model=List[StudentOut])
async def get_students_by_class(
    payload: ClassStudentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify school ownership
    if current_user["school_id"] != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only access students from your own school"
        )

    # Role-based authorization
    if current_user["role"] not in [
        SchoolUserRole.TEACHER,
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to view students"
        )

    # Get students with class information
    students = await db.execute(
        select(SchoolUser).where(
            SchoolUser.school_id == payload.school_id,
            SchoolUser.class_id == payload.class_id,
            SchoolUser.role == SchoolUserRole.STUDENT
        ).order_by(SchoolUser.name)  # Added ordering for consistency
    )
    return students.scalars().all()


# --- ADD SUBJECT TO SCHOOL ---
@router.post("/add-subject", response_model=SchoolSubjectOut)
async def add_subject_to_school(
    payload: SchoolSubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Role validation
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to add subjects"
        )

    # School ownership verification
    if current_user["school_id"] != payload.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subjects can only be added to your own school"
        )

    # Create and add new subject
    subject = SchoolSubject(
        name=payload.name,
        school_id=payload.school_id
    )
    db.add(subject)

    try:
        await db.commit()
        await db.refresh(subject)
        return subject
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subject with this name already exists in your school"
        )


# --- GET ALL SUBJECTS FOR A SCHOOL ---
@router.get("/{school_id}/subjects", response_model=List[SchoolSubjectOut])
async def get_all_subjects(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify school access
    if current_user["school_id"] != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view subjects from your own school"
        )

    # Role validation
    if current_user["role"] not in [
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN,
        SchoolUserRole.TEACHER
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to view subjects"
        )

    # Get and return subjects
    subjects = await db.execute(
        select(SchoolSubject)
        .where(SchoolSubject.school_id == school_id)
        .order_by(SchoolSubject.name)  # Added ordering
    )
    return subjects.scalars().all()


# --- GET ALL ADMINS FOR A SCHOOL ---
@router.get("/{school_id}/admins", response_model=List[SchoolUserOut])
async def get_school_admins(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify the user has access to this school's data
    if current_user["school_id"] != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access data from your own school"
        )

    # Only school_superadmin can access this endpoint
    if current_user["role"] != SchoolUserRole.SCHOOL_SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school_superadmin can view all admins of a school"
        )

    # Get all admins of the school
    result = await db.execute(
        select(SchoolUser).where(
            SchoolUser.school_id == school_id,
            SchoolUser.role == SchoolUserRole.SCHOOL_ADMIN
        ).order_by(SchoolUser.name)
    )
    admins = result.scalars().all()
    
    return admins


# --- GET ALL STUDENTS(By classes) FOR A SCHOOL ---
@router.get("/{school_id}/students-with-classes", response_model=List[StudentOut])
async def get_all_students_with_classes(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify the user has access to this school's data
    if current_user["school_id"] != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access data from your own school"
        )

    # Only school admins and superadmins can access this endpoint
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school administrators can view all students"
        )

    # Get all students with their class information
    result = await db.execute(
        select(SchoolUser).where(
            SchoolUser.school_id == school_id,
            SchoolUser.role == SchoolUserRole.STUDENT
        ).order_by(SchoolUser.class_id, SchoolUser.name)
    )
    students = result.scalars().all()
    
    return students


# --- GET ALL TEACHERS FOR A SCHOOL (ID, NAME, EMAIL) ---
@router.get("/{school_id}/teachers", response_model=List[SchoolTeacherOut])
async def get_all_teachers(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify the user has access to this school's data
    if current_user["school_id"] != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access data from your own school"
        )

    # Only school admins, superadmins and teachers can access this endpoint
    if current_user["role"] not in [
        SchoolUserRole.SCHOOL_ADMIN, 
        SchoolUserRole.SCHOOL_SUPERADMIN,
        SchoolUserRole.TEACHER
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to view teachers"
        )

    # Get all teachers of the school with only id, name, email
    result = await db.execute(
        select(SchoolUser).where(
            SchoolUser.school_id == school_id,
            SchoolUser.role == SchoolUserRole.TEACHER
        ).order_by(SchoolUser.name)
    )
    teachers = result.scalars().all()
    
    return teachers