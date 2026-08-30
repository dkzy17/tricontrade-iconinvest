import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import SessionLocal, connect_db, close_db
from app.core.security import hash_password
from app.models.collections import User


ADMINS = [
    {
        "email": "admin@tricontrade.com",
        "password": os.getenv("TRICONTRADE_ADMIN_PASSWORD"),
        "f_name": "Admin",
        "l_name": "One",
    },
    {
        "email": "super@tricontrade.com",
        "password": os.getenv("TRICONTRADE_SUPERADMIN_PASSWORD"),
        "f_name": "Admin",
        "l_name": "Two",
    },
]


async def main():
    for admin in ADMINS:
        if not admin["password"]:
            raise RuntimeError(
                f"Missing password environment variable for {admin['email']}"
            )

    await connect_db()

    try:
        async with SessionLocal() as db:
            for admin in ADMINS:
                email = admin["email"].lower()

                result = await db.execute(
                    select(User).where(User.email == email)
                )

                existing = result.scalar_one_or_none()

                if existing:
                    existing.role = "admin"
                    existing.verified = True
                    existing.password = hash_password(admin["password"])

                    print(f"Updated existing admin: {email}")

                else:
                    user = User(
                        email=email,
                        password=hash_password(admin["password"]),
                        f_name=admin["f_name"],
                        l_name=admin["l_name"],
                        phone="",
                        country="Nigeria",
                        balance=0,
                        profit=0,
                        deposit_balance=0,
                        referral_balance=0,
                        withdraw_balance=0,
                        invest_balance=0,
                        currency="usd",
                        verified=True,
                        role="admin",
                        referral_id=None,
                        referrer_id=None,
                    )

                    db.add(user)

                    print(f"Created admin: {email}")

            await db.commit()

    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())