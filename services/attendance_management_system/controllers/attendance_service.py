from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
import uuid

from shared.db import get_db
from shared.auth import get_current_user
from services.user_management.models.users import SchoolUser, SchoolUserRole
from services.user_management.models.classes import SchoolClass
from services.attendance_management_system.models.attendance import Attendance, AttendanceStatus
from services.attendance_management_system.schemas.attendance import (
    DailyAttendanceCreate,
    DailyAttendanceResponse,
    AttendanceOut,
    StudentAttendanceRecord,
    AttendanceStatus as SchemaAttendanceStatus
)

router = APIRouter(prefix="/attendance", tags=["Attendance Management"])


async def _get_class_students(db: AsyncSession, class_id: uuid.UUID) -> List[SchoolUser]:
    result = await db.execute(
        select(SchoolUser).where(
            and_(
                SchoolUser.class_id == class_id,
                SchoolUser.role == SchoolUserRole.STUDENT,
                SchoolUser.is_active == True
            )
        )
    )
    return result.scalars().all()


@router.post("/daily", response_model=DailyAttendanceResponse)
async def record_daily_attendance(
    attendance_data: DailyAttendanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Record daily attendance for a class. 
    Only students with non-present status need to be included in the records.
    All other students will be automatically marked as present.
    """
    teacher_id = uuid.UUID(current_user["id"])
    school_id = current_user["school_id"]

    # Get class details and verify access
    class_result = await db.execute(
        select(SchoolClass).where(
            and_(
                SchoolClass.id == attendance_data.class_id,
                SchoolClass.school_id == school_id
            )
        )
    )
    school_class = class_result.scalar_one_or_none()
    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found or access denied"
        )

    # Optional: If SchoolClass has a `teacher_id`, verify ownership
    if school_class.teacher_id != teacher_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the assigned teacher for this class"
        )

    # Get all active students in the class
    students = await _get_class_students(db, attendance_data.class_id)
    if not students:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active students found in this class"
        )

    # Create a map of student_id to attendance input data
    attendance_input_map = {
        record.student_id: record for record in attendance_data.records
    }

    # Get all existing attendance records for the class and date in a single query
    existing_attendance_result = await db.execute(
        select(Attendance).where(
            and_(
                Attendance.class_id == attendance_data.class_id,
                Attendance.date == attendance_data.date
            )
        )
    )
    existing_attendance_map = {
        record.student_id: record for record in existing_attendance_result.scalars()
    }

    attendances = []
    for student in students:
        record = attendance_input_map.get(student.id)

        if record:
            status_val = record.status
            arrival_time = record.arrival_time
            notes = record.notes
        else:
            status_val = AttendanceStatus.PRESENT
            arrival_time = None
            notes = None

        existing = existing_attendance_map.get(student.id)
        if existing:
            existing.status = status_val
            existing.arrival_time = arrival_time
            existing.notes = notes
            existing.recorded_by = teacher_id
            attendances.append(existing)
        else:
            new_attendance = Attendance(
                school_id=school_id,
                class_id=attendance_data.class_id,
                date=attendance_data.date,
                student_id=student.id,
                status=status_val,
                recorded_by=teacher_id,
                arrival_time=arrival_time,
                notes=notes
            )
            db.add(new_attendance)
            attendances.append(new_attendance)

    await db.commit()

    # Prepare student + teacher names
    student_ids = [student.id for student in students]
    users_result = await db.execute(
        select(SchoolUser).where(
            or_(
                SchoolUser.id.in_(student_ids),
                SchoolUser.id == teacher_id
            )
        )
    )
    users = {user.id: user for user in users_result.scalars()}

    response_attendances = []
    for attendance in attendances:
        student = users.get(attendance.student_id)
        recorder = users.get(attendance.recorded_by)

        response_attendances.append(AttendanceOut(
            id=attendance.id,
            student_id=attendance.student_id,
            student_name=student.name if student else "Unknown",
            status=attendance.status,
            arrival_time=attendance.arrival_time,
            notes=attendance.notes,
            recorded_by=attendance.recorded_by,
            recorded_by_name=recorder.name if recorder else "Unknown",
            created_at=attendance.created_at.isoformat()
        ))

    return DailyAttendanceResponse(
        class_id=school_class.id,
        class_name=f"{school_class.class_name} {school_class.section}",
        date=attendance_data.date,
        attendances=response_attendances
    )
