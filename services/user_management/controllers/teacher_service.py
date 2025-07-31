from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from services.user_management.models.teachers import ClassTeacher
from services.user_management.models.users import SchoolUser, SchoolUserRole
from services.user_management.models.subjects import SchoolSubject, ClassSubject
from services.user_management.models.classes import SchoolClass
from services.user_management.schemas.teachers import (
    ClassTeacherCreate, 
    ClassTeacherOut,
    ClassWithTeacherResponse,
    TeacherSubjectAssignmentOut
)
from shared.db import get_db
from shared.auth import get_current_user
import uuid

router = APIRouter(prefix="/teachers", tags=["Teacher Assignments"])

# --- GET ALL CLASSES WITH TEACHER INFO ---
@router.get("/school-class-teachers", response_model=List[ClassWithTeacherResponse])
async def get_classes_with_teachers(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all classes with their teacher assignments (if any).
    Efficient single query with LEFT JOIN.
    """
    result = await db.execute(
        select(
            SchoolClass,
            SchoolUser.id.label("teacher_id"),
            SchoolUser.name.label("teacher_name")
        )
        .select_from(SchoolClass)
        .outerjoin(ClassTeacher, SchoolClass.id == ClassTeacher.class_id)
        .outerjoin(SchoolUser, ClassTeacher.teacher_id == SchoolUser.id)
        .where(SchoolClass.school_id == current_user["school_id"])
        .order_by(SchoolClass.class_name)
    )
    
    return [{
        "class_id": class_.id,
        "class_name": class_.class_name,
        "teacher_id": teacher_id,
        "section": class_.section,  
        "teacher_name": teacher_name or "No teacher assigned"
    } for class_, teacher_id, teacher_name in result.all()]


# --- UPSERT CLASS TEACHER ASSIGNMENT ---
@router.post("/assign-class-teacher", response_model=ClassTeacherOut)
async def assign_class_teacher(
    data: ClassTeacherCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Assign or update a class teacher assignment.
    Automatically handles both new assignments and updates.
    """
    # Admin authorization
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Verify teacher exists and belongs to school
    teacher = await db.get(SchoolUser, data.teacher_id)
    if not teacher or teacher.role != SchoolUserRole.TEACHER or teacher.school_id != current_user["school_id"]:
        raise HTTPException(status_code=404, detail="Teacher not found or unauthorized")

    # Verify class exists and belongs to school
    school_class = await db.get(SchoolClass, data.class_id)
    if not school_class or school_class.school_id != current_user["school_id"]:
        raise HTTPException(status_code=404, detail="Class not found or unauthorized")

    # Check if teacher is already assigned elsewhere
    existing_assignment = await db.execute(
        select(ClassTeacher)
        .where(
            ClassTeacher.teacher_id == data.teacher_id,
            ClassTeacher.class_id != data.class_id
        )
    )
    if existing_assignment.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="This teacher is already assigned to another class"
        )

    # Find existing assignment for this class
    current_assignment = await db.execute(
        select(ClassTeacher)
        .where(ClassTeacher.class_id == data.class_id)
    )
    current_assignment = current_assignment.scalar_one_or_none()

    if current_assignment:
        # Update existing assignment
        current_assignment.teacher_id = data.teacher_id
    else:
        # Create new assignment
        current_assignment = ClassTeacher(**data.dict())
        db.add(current_assignment)

    await db.commit()
    await db.refresh(current_assignment)
    return current_assignment

# --- REMOVE CLASS TEACHER ASSIGNMENT ---
@router.delete("/remove-assignment/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_class_teacher(
    class_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Remove teacher assignment from a class.
    """
    # Admin authorization
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Verify class exists
    school_class = await db.get(SchoolClass, class_id)
    if not school_class or school_class.school_id != current_user["school_id"]:
        raise HTTPException(status_code=404, detail="Class not found or unauthorized")

    # Find and delete assignment
    assignment = await db.execute(
        select(ClassTeacher)
        .where(ClassTeacher.class_id == class_id)
    )
    assignment = assignment.scalar_one_or_none()

    if assignment:
        await db.delete(assignment)
        await db.commit()

    return None  # 204 No Content

# --- GET TEACHER'S CLASS ASSIGNMENT ---
@router.get("/teacher-class/{teacher_id}", response_model=Optional[ClassTeacherOut])
async def get_teacher_assignment(
    teacher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the class assignment for a specific teacher.
    """
    # Verify teacher exists and belongs to school
    teacher = await db.get(SchoolUser, teacher_id)
    if not teacher or teacher.school_id != current_user["school_id"]:
        raise HTTPException(status_code=404, detail="Teacher not found or unauthorized")

    # Get assignment
    assignment = await db.execute(
        select(ClassTeacher)
        .where(ClassTeacher.teacher_id == teacher_id)
        .options(selectinload(ClassTeacher.school_class))
    )
    return assignment.scalar_one_or_none()


# --- GET TEACHER'S SUBJECTS AND CLASSES ---
@router.get("/my-assignments", response_model=List[TeacherSubjectAssignmentOut])
async def get_my_teacher_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Only teachers can access this endpoint
    if current_user["role"] != SchoolUserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can access their assignments"
        )

    # Get all class subjects assigned to this teacher
    result = await db.execute(
        select(
            ClassSubject.class_id,
            SchoolClass.class_name,
            SchoolClass.section,
            ClassSubject.subject_id,
            SchoolSubject.name.label("subject_name"),
            ClassSubject.is_optional
        )
        .join(SchoolClass, ClassSubject.class_id == SchoolClass.id)
        .join(SchoolSubject, ClassSubject.subject_id == SchoolSubject.id)
        .where(
            ClassSubject.teacher_id == current_user["user_id"],
            SchoolClass.school_id == current_user["school_id"]  # Security check
        )
        .order_by(SchoolClass.class_name, SchoolClass.section, SchoolSubject.name)
    )
    
    assignments = []
    for row in result.all():
        assignments.append({
            "class_id": row.class_id,
            "class_display_name": f"{row.class_name} {row.section}",  # Combine class_name and section
            "subject_id": row.subject_id,
            "subject_name": row.subject_name,
            "is_optional": row.is_optional
        })
    
    return assignments