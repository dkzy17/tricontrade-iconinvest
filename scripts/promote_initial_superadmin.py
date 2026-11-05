import asyncio
import sys
from pathlib import Path

# Make the project root importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, connect_db, close_db
from app.models.collections import User
from app.core.admin_audit import record_admin_action


async def main():
    email = (settings.initial_superadmin_email or "").strip().lower()

    if not email:
        raise RuntimeError("INITIAL_SUPERADMIN_EMAIL is not configured.")

    await connect_db()

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(User)
                .where(User.email == email)
                .with_for_update()
            )
            user = result.scalar_one_or_none()

            if user is None:
                raise RuntimeError("Initial superadmin account was not found.")

            if user.suspended:
                raise RuntimeError("Cannot promote a suspended account.")

            if user.role == "superadmin":
                print("Initial account is already superadmin.")
                return

            if user.role != "admin":
                raise RuntimeError(
                    "Initial account must already have the admin role."
                )

            previous_role = user.role
            user.role = "superadmin"

            record_admin_action(
                db,
                user,
                "admin.initial_superadmin_promoted",
                target=user,
                details={
                    "source": "initial_bootstrap",
                    "previous_role": previous_role,
                    "new_role": "superadmin",
                },
            )

            await db.commit()
            print("Initial superadmin promotion completed.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
