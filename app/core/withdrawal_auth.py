from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token


withdrawal_bearer = HTTPBearer(auto_error=True)


async def require_withdrawal_authorization(
    credentials: HTTPAuthorizationCredentials = Depends(withdrawal_bearer),
) -> dict:
    try:
        payload = decode_access_token(
            credentials.credentials
        )

        if payload.get("purpose") != "withdrawal_verification":
            raise ValueError("Invalid token purpose")

        user_id = payload.get("sub")
        verification_id = payload.get(
            "verification_id"
        )

        if not user_id or verification_id is None:
            raise ValueError("Missing withdrawal claims")

        return {
            "user_id": int(user_id),
            "verification_id": int(verification_id),
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired withdrawal authorization",
        )
