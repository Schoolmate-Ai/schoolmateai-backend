from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from services.user_management.models.users import SchoolUser
from services.user_management.schemas.users import (
    SchoolUserLoginRequest,
    SchoolUserLoginResponse
)
from shared.auth import verify_password, create_access_token
from shared.db import get_db

router = APIRouter(prefix="/school", tags=["SchoolUser"])

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
