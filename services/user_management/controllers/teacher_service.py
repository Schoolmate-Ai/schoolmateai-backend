from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import text

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
    Get all classes with their assigned teacher (if any).
    Uses direct reference from class_teacher_id in SchoolClass.
    """
    result = await db.execute(
        select(SchoolClass, SchoolUser)
        .outerjoin(SchoolUser, SchoolUser.id == SchoolClass.class_teacher_id)
        .where(SchoolClass.school_id == current_user["school_id"])
        .order_by(SchoolClass.class_name)
    )

    return [
        {
            "class_id": school_class.id,
            "class_name": school_class.class_name,
            "section": school_class.section,
            "teacher_id": teacher.id if teacher else None,
            "teacher_name": teacher.name if teacher else "No teacher assigned"
        }
        for school_class, teacher in result.all()
    ]

# --- UPSERT CLASS TEACHER ASSIGNMENT ---
@router.post("/assign-class-teacher", response_model=ClassTeacherOut)
async def assign_class_teacher(
    data: ClassTeacherCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Assign or update a class teacher to a class (in-place, no separate table).
    """
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    teacher = await db.get(SchoolUser, data.teacher_id)
    if not teacher or teacher.role != SchoolUserRole.TEACHER or teacher.school_id != current_user["school_id"]:
        raise HTTPException(status_code=404, detail="Teacher not found or unauthorized")

    school_class = await db.get(SchoolClass, data.class_id)
    if not school_class or school_class.school_id != current_user["school_id"]:
        raise HTTPException(status_code=404, detail="Class not found or unauthorized")

    conflict_query = await db.execute(
        select(SchoolClass).where(
            SchoolClass.class_teacher_id == data.teacher_id,
            SchoolClass.id != data.class_id
        )
    )
    if conflict_query.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="This teacher is already assigned to another class"
        )

    # ✅ Perform DB operations directly (NO nested transaction block)
    try:
        if school_class.class_teacher_id and school_class.class_teacher_id != data.teacher_id:
            await db.execute(
                text("""
                    UPDATE school_users 
                    SET profile_data = jsonb_set(
                        COALESCE(profile_data, '{}'::jsonb),
                        '{isClassteacher}',
                        'false'::jsonb,
                        true
                    )
                    WHERE id = :old_teacher_id
                """).bindparams(old_teacher_id=school_class.class_teacher_id)
            )

        await db.execute(
            text("""
                UPDATE school_users 
                SET profile_data = jsonb_set(
                    COALESCE(profile_data, '{}'::jsonb),
                    '{isClassteacher}',
                    'true'::jsonb,
                    true
                )
                WHERE id = :teacher_id
            """).bindparams(teacher_id=data.teacher_id)
        )

        school_class.class_teacher_id = data.teacher_id
        db.add(school_class)

        await db.commit()
        await db.refresh(school_class)

        return ClassTeacherOut(
            class_id=school_class.id,
            teacher_id=data.teacher_id
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error assigning class teacher: {str(e)}")


# --- REMOVE CLASS TEACHER ASSIGNMENT ---
@router.delete("/unassign-class-teacher/{class_id}")
async def unassign_class_teacher(
    class_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Unassign the class teacher from a given class (sets class_teacher_id to null).
    """
    if current_user["role"] not in [SchoolUserRole.SCHOOL_ADMIN, SchoolUserRole.SCHOOL_SUPERADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch the class
    school_class = await db.get(SchoolClass, class_id)
    if not school_class or school_class.school_id != current_user["school_id"]:
        raise HTTPException(status_code=404, detail="Class not found or unauthorized")

    if not school_class.class_teacher_id:
        raise HTTPException(status_code=400, detail="No class teacher assigned to this class")

    try:
        # Set isClassteacher = false in teacher's profile_data
        await db.execute(
            text("""
                UPDATE school_users 
                SET profile_data = jsonb_set(
                    COALESCE(profile_data, '{}'::jsonb),
                    '{isClassteacher}',
                    'false'::jsonb,
                    true
                )
                WHERE id = :teacher_id
            """).bindparams(teacher_id=school_class.class_teacher_id)
        )

        # Set class_teacher_id to NULL
        school_class.class_teacher_id = None
        db.add(school_class)

        await db.commit()

        return {"message": "Class teacher removed"}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error unassigning class teacher: {str(e)}")



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
