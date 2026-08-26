from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.api.auth import public_user
from app.schemas.auth import SigninIn
from app.models.collections import User

router = APIRouter()


@router.post("/signin")
async def admin_signin(
    data: SigninIn,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.lower()

    result = await db.execute(
        select(User).where(
            User.email == email,
            User.role == "admin",
        )
    )

    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin email or password",
        )

    if not verify_password(data.password, admin.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin email or password",
        )

    token = create_access_token(
        str(admin.id),
        "admin",
    )

    return {
        "status": "success",
        "token": token,
        "admin": public_user(admin),
    }