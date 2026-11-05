from fastapi import APIRouter, Depends, HTTPException, status
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
    email = data.email.lower().strip()

    result = await db.execute(
        select(User).where(
            User.email == email,
            User.role.in_(["admin", "superadmin"]),
        )
    )

    admin = result.scalar_one_or_none()

    if not admin or not verify_password(data.password, admin.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin email or password",
        )

    if admin.suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account suspended",
        )

    token = create_access_token(
        str(admin.id),
        admin.role,
    )

    return {
        "status": "success",
        "token": token,
        "admin": public_user(admin),
    }
