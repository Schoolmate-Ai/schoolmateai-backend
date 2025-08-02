from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Any
from sqlalchemy import case, and_, or_
from uuid import UUID

from shared.db import get_db
from shared.auth import get_current_user
from services.user_management.models.users import SchoolUserRole, SchoolUser
from services.user_management.models.subjects import SchoolSubject, ClassSubject, StudentSubject
from services.user_management.models.classes import SchoolClass
from services.user_management.schemas.subjects import (
    ClassSubjectCreate,
    ClassSubjectOut,
    SubjectMappingInput,
    StudentSubjectOut,
    StudentSubjectCreate,
    ClassSubjectDetailOut,
    StudentSubjectDetailOut,
    AssignTeacherToSubject
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
        teacher_id=payload.teacher_id,
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
@router.get("/by-class/{class_id}", response_model=List[ClassSubjectDetailOut])
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

    # Get all subject mappings for the class with subject names
    result = await db.execute(
    select(
        ClassSubject.id,
        ClassSubject.subject_id,
        SchoolSubject.name.label("subject_name"),
        ClassSubject.is_optional,
        ClassSubject.teacher_id,
        SchoolUser.name.label("teacher_name")  
    )
    .join(SchoolSubject, ClassSubject.subject_id == SchoolSubject.id)
    .outerjoin(SchoolUser, ClassSubject.teacher_id == SchoolUser.id)  # Add this
    .where(ClassSubject.class_id == class_id)
)
    
    class_subjects = result.all()
    return class_subjects


# --- GET ALL CLASSES WITH SUBJECTS FOR SCHOOL ---
@router.get("/all-classes-with-subjects", response_model=Dict[str, List[Dict[str, Any]]])
async def get_classes_with_subjects(
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
            detail="Not authorized to view school subjects"
        )

    # Get all classes with their subjects
    result = await db.execute(
        select(
            SchoolClass.id.label("class_id"),
            SchoolClass.class_name,
            SchoolClass.section,
            ClassSubject.subject_id,
            SchoolSubject.name.label("subject_name"),
            ClassSubject.is_optional,
            ClassSubject.teacher_id,
            SchoolUser.name.label("teacher_name")
        )
        .join(ClassSubject, SchoolClass.id == ClassSubject.class_id)
        .join(SchoolSubject, ClassSubject.subject_id == SchoolSubject.id)
        .outerjoin(SchoolUser, ClassSubject.teacher_id == SchoolUser.id)
        .where(SchoolClass.school_id == current_user["school_id"])
        .order_by(SchoolClass.class_name, SchoolClass.section, SchoolSubject.name)
    )

    # Organize results by class
    classes_with_subjects = {}
    for row in result.all():
        class_key = f"{row.class_name} {row.section}"
        subject_info = {
            "subject_id": row.subject_id,
            "subject_name": row.subject_name,
            "is_optional": row.is_optional,
            "teacher_id": row.teacher_id,
            "teacher_name": row.teacher_name
        }
        
        if class_key not in classes_with_subjects:
            classes_with_subjects[class_key] = []
        classes_with_subjects[class_key].append(subject_info)
    
    return classes_with_subjects


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


# --- ASSIGN OPTIONAL SUBJECT FROM CLASS ---
@router.post("/assign-optional", response_model=StudentSubjectOut)
async def assign_optional_subject(
    payload: StudentSubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Authorization - teachers/admins can assign subjects
    if current_user["role"] not in [
        SchoolUserRole.TEACHER,
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and administrators can assign optional subjects"
        )

    # Verify student exists and belongs to same school
    student = await db.execute(
        select(SchoolUser)
        .where(
            SchoolUser.id == payload.student_id,
            SchoolUser.school_id == current_user["school_id"]
        )
    )
    student = student.scalars().first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found in your school"
        )

    # Verify class_subject exists and is optional
    class_subject = await db.execute(
        select(ClassSubject)
        .join(SchoolClass, ClassSubject.class_id == SchoolClass.id)
        .where(
            ClassSubject.id == payload.class_subject_id,
            SchoolClass.school_id == current_user["school_id"],
            ClassSubject.is_optional == True  # Must be optional subject
        )
    )
    class_subject = class_subject.scalars().first()
    
    if not class_subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Optional subject not found or not available for this student"
        )

    # Check if already assigned
    existing = await db.execute(
        select(StudentSubject).where(
            StudentSubject.student_id == payload.student_id,
            StudentSubject.class_subject_id == payload.class_subject_id
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This optional subject is already assigned to the student"
        )

    # Create assignment
    assignment = StudentSubject(
        student_id=payload.student_id,
        class_subject_id=payload.class_subject_id
    )
    db.add(assignment)
    
    try:
        await db.commit()
        await db.refresh(assignment)
        return assignment
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error assigning optional subject"
        )
    

# --- GET OPTIONAL SUBJECT OF A STUDENT ---
@router.get("/student/{student_id}/optional", response_model=List[StudentSubjectOut])
async def get_student_optional_subjects(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify student exists and belongs to same school
    student = await db.execute(
        select(SchoolUser)
        .where(
            SchoolUser.id == student_id,
            SchoolUser.school_id == current_user["school_id"]
        )
    )
    if not student.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found in your school"
        )

    # Get optional subjects
    result = await db.execute(
        select(StudentSubject)
        .where(StudentSubject.student_id == student_id)
    )
    return result.scalars().all()


# --- DELETE OPTIONAL SUBJECT ---
@router.delete("/remove-optional/{assignment_id}")
async def remove_optional_subject(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Authorization - teachers/admins can remove assignments
    if current_user["role"] not in [
        SchoolUserRole.TEACHER,
        SchoolUserRole.SCHOOL_ADMIN,
        SchoolUserRole.SCHOOL_SUPERADMIN
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and administrators can remove optional subjects"
        )

    # Get assignment with verification
    assignment = await db.execute(
        select(StudentSubject)
        .join(SchoolUser, StudentSubject.student_id == SchoolUser.id)
        .join(ClassSubject, StudentSubject.class_subject_id == ClassSubject.id)
        .join(SchoolClass, ClassSubject.class_id == SchoolClass.id)
        .where(
            StudentSubject.id == assignment_id,
            SchoolUser.school_id == current_user["school_id"],
            SchoolClass.school_id == current_user["school_id"]
        )
    )
    assignment = assignment.scalars().first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found or not authorized"
        )

    await db.delete(assignment)
    try:
        await db.commit()
        return {"message": "Optional subject removed successfully"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error removing optional subject"
        )
    

# --- GET ALL(OPT + COMP.) SUBJECT OF A STUDENT ---
@router.get("/student/{student_id}/all-subjects", response_model=Dict[str, List[StudentSubjectDetailOut]])
async def get_all_student_subjects(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify student exists and belongs to same school
    student = await db.execute(
        select(SchoolUser)
        .where(
            SchoolUser.id == student_id,
            SchoolUser.school_id == current_user["school_id"]
        )
    )
    student = student.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Modified query to include subject names
    result = await db.execute(
        select(
            ClassSubject.id,
            ClassSubject.subject_id,
            SchoolSubject.name.label("subject_name"),
            ClassSubject.is_optional,
            case(
                (ClassSubject.is_optional == True, "optional"),
                else_="compulsory"
            ).label("subject_type")
        )
        .join(SchoolSubject, ClassSubject.subject_id == SchoolSubject.id)
        .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
        .outerjoin(
            StudentSubject,
            and_(
                StudentSubject.class_subject_id == ClassSubject.id,
                StudentSubject.student_id == student_id
            )
        )
        .where(
            SchoolClass.id == student.class_id,
            or_(
                ClassSubject.is_optional == False,  # Compulsory
                and_(
                    ClassSubject.is_optional == True,
                    StudentSubject.id.is_not(None)  # Optional and assigned
                )
            )
        )
    )
    
    # Organize results with subject names
    subjects = {"compulsory": [], "optional": []}
    for row in result.all():
        subject_data = {
            "subject_id": row.subject_id,
            "subject_name": row.subject_name,
            "is_optional": row.is_optional
        }
        if row.subject_type == "compulsory":
            subjects["compulsory"].append(subject_data)
        else:
            subjects["optional"].append(subject_data)
    
    return subjects


# --- BULK ASSIGN OPTIONAL SUBJECT TO LIST OF STUDENTS ---
@router.post("/bulk-assign-optional-to-students")
async def bulk_assign_optional_subject(
    class_subject_id: UUID,
    student_ids: List[UUID],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify subject exists, is optional, and belongs to school (1 query)
    subject_result = await db.execute(
        select(ClassSubject)
        .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
        .where(
            ClassSubject.id == class_subject_id,
            ClassSubject.is_optional == True,
            SchoolClass.school_id == current_user["school_id"]
        )
    )
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Optional subject not found")

    # Get all valid students in one query
    valid_students = await db.execute(
        select(SchoolUser.id)
        .where(
            SchoolUser.id.in_(student_ids),
            SchoolUser.school_id == current_user["school_id"],
            SchoolUser.class_id == subject.class_id
        )
    )
    valid_student_ids = {s.id for s in valid_students.scalars().all()}

    # Get existing assignments in one query
    existing_assignments = await db.execute(
        select(StudentSubject.student_id)
        .where(
            StudentSubject.class_subject_id == class_subject_id,
            StudentSubject.student_id.in_(valid_student_ids)
        )
    )
    existing_student_ids = {a.student_id for a in existing_assignments.scalars().all()}

    # Prepare new assignments
    new_assignments = [
        StudentSubject(
            student_id=student_id,
            class_subject_id=class_subject_id
        )
        for student_id in valid_student_ids
        if student_id not in existing_student_ids
    ]

    # Bulk insert (1 query)
    if new_assignments:
        db.add_all(new_assignments)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Error creating assignments"
            )

    # Prepare response
    success_ids = set(new_assignments.student_id for new_assignments in new_assignments)
    failed = []
    
    for student_id in student_ids:
        if student_id not in valid_student_ids:
            failed.append({"student_id": student_id, "reason": "Invalid student"})
        elif student_id in existing_student_ids:
            failed.append({"student_id": student_id, "reason": "Already assigned"})
    
    return {
        "success": list(success_ids),
        "failed": failed,
        "message": f"Assigned to {len(success_ids)} students"
    }


# --- ASSIGN TEACHERS TO SUBJECTS ---
@router.post("/assign-teacher-to-subject", response_model=ClassSubjectOut)
async def assign_teacher_to_subject(
    payload: AssignTeacherToSubject,
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
            detail="Only admins can assign teachers to subjects"
        )

    # Verify the teacher exists and is a teacher in the same school
    teacher = await db.execute(
        select(SchoolUser).where(
            SchoolUser.id == payload.teacher_id,
            SchoolUser.school_id == current_user["school_id"],
            SchoolUser.role == SchoolUserRole.TEACHER
        ))
    teacher = teacher.scalars().first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found in your school"
        )

    # Verify the class-subject mapping exists
    class_subject = await db.execute(
        select(ClassSubject)
        .join(SchoolClass, ClassSubject.class_id == SchoolClass.id)
        .where(
            ClassSubject.id == payload.class_subject_id,
            SchoolClass.school_id == current_user["school_id"]
        ))
    class_subject = class_subject.scalars().first()
    
    if not class_subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class-subject mapping not found"
        )

    # Assign the teacher
    class_subject.teacher_id = payload.teacher_id
    
    try:
        await db.commit()
        await db.refresh(class_subject)
        return class_subject
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error assigning teacher to subject"
        )