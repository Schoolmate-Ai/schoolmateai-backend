from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID

from shared.db import get_db
from shared.auth import get_current_user
from services.user_management.models.users import SchoolUserRole
from services.user_management.models.subjects import SchoolSubject, ClassSubject
from services.user_management.models.classes import SchoolClass
from services.user_management.schemas.subjects import (
    ClassSubjectCreate,
    ClassSubjectOut,
    SubjectMappingInput
)

router = APIRouter(prefix="/subjects", tags=["Subjects"])

# --- ADD SUBJECT TO CLASS ---
@router.post("/map-to-class", response_model=ClassSubjectOut)
async def add_subject_to_class(
    payload: ClassSubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Check authorization - only admin/superadmin/teacher can map subjects to classes
    if current_user["role"] not in [
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN,
        SchoolUserRole.TEACHER
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to map subjects to classes"
        )

    # Verify the subject exists and belongs to user's school
    subject_result = await db.execute(
        select(SchoolSubject)
        .where(SchoolSubject.id == payload.subject_id)
    )
    subject = subject_result.scalars().first()
    if not subject or subject.school_id != current_user["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found in your school"
        )

    # Verify the class exists and belongs to user's school
    class_result = await db.execute(
        select(SchoolClass)
        .where(SchoolClass.id == payload.class_id)
    )
    school_class = class_result.scalars().first()
    if not school_class or school_class.school_id != current_user["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found in your school"
        )

    # Check if this subject is already mapped to the class
    existing_mapping = await db.execute(
        select(ClassSubject).where(
            ClassSubject.class_id == payload.class_id,
            ClassSubject.subject_id == payload.subject_id
        ))
    if existing_mapping.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This subject is already mapped to this class"
        )

    # Create the mapping
    class_subject = ClassSubject(
        class_id=payload.class_id,
        subject_id=payload.subject_id,
        is_optional=payload.is_optional
    )

    db.add(class_subject)
    try:
        await db.commit()
        await db.refresh(class_subject)
        return class_subject
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error creating subject-class mapping"
        )


# --- BULK ADD SUBJECTS TO CLASS ---
@router.post("/bulk-map-to-class/{class_id}", response_model=List[ClassSubjectOut])
async def bulk_add_subjects_to_class(
    class_id: UUID,
    subjects: List[SubjectMappingInput],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Authorization check
    if current_user["role"] not in [
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN,
        SchoolUserRole.TEACHER
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to map subjects to classes"
        )

    # Verify the class exists and belongs to user's school
    class_result = await db.execute(
        select(SchoolClass)
        .where(SchoolClass.id == class_id)
    )
    school_class = class_result.scalars().first()
    if not school_class or school_class.school_id != current_user["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found in your school"
        )

    created_mappings = []
    
    for subject in subjects:
        # Verify the subject exists and belongs to the same school
        subject_result = await db.execute(
            select(SchoolSubject).where(SchoolSubject.id == subject.subject_id))
        db_subject = subject_result.scalars().first()
        
        if not db_subject:
            continue  # Skip if subject doesn't exist
        if db_subject.school_id != school_class.school_id:
            continue  # Skip if subject belongs to different school

        # Check if mapping already exists
        existing_mapping = await db.execute(
            select(ClassSubject).where(
                ClassSubject.class_id == class_id,
                ClassSubject.subject_id == subject.subject_id
            ))
        if existing_mapping.scalars().first():
            continue  # Skip if already exists

        # Create new mapping
        class_subject = ClassSubject(
            class_id=class_id,
            subject_id=subject.subject_id,
            is_optional=subject.is_optional
        )
        db.add(class_subject)
        created_mappings.append(class_subject)

    try:
        await db.commit()
        # Refresh all created mappings
        for mapping in created_mappings:
            await db.refresh(mapping)
        return created_mappings
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error creating some subject-class mappings"
        )


# --- GET SUBJECTS FOR CLASS ---
@router.get("/by-class/{class_id}", response_model=List[ClassSubjectOut])
async def get_subjects_for_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Authorization check
    if current_user["role"] not in [
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN,
        SchoolUserRole.TEACHER,
        SchoolUserRole.STUDENT
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view class subjects"
        )

    # Verify the class exists and belongs to user's school
    class_result = await db.execute(
        select(SchoolClass)
        .where(SchoolClass.id == class_id)
    )
    school_class = class_result.scalars().first()
    if not school_class or school_class.school_id != current_user["school_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found in your school"
        )

    # Get all subject mappings for the class
    result = await db.execute(
        select(ClassSubject).where(ClassSubject.class_id == class_id))
    class_subjects = result.scalars().all()
    return class_subjects


# --- REMOVE SUBJECT FROM CLASS ---
@router.delete("/remove-from-class/{mapping_id}")
async def remove_subject_from_class(
    mapping_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Authorization check
    if current_user["role"] not in [
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can remove subjects from classes"
        )

    # Get the mapping
    result = await db.execute(
        select(ClassSubject).where(ClassSubject.id == mapping_id))
    mapping = result.scalars().first()
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject-class mapping not found"
        )

    # Verify both class and subject belong to user's school
    if (mapping.school_class.school_id != current_user["school_id"] or 
        mapping.school_subject.school_id != current_user["school_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify mappings from other schools"
        )

    # Delete the mapping
    await db.delete(mapping)
    try:
        await db.commit()
        return {"message": "Subject successfully removed from class"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error removing subject from class"
        )