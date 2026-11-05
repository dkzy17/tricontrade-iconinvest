import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, connect_db, close_db
from app.core.security import hash_password
from app.models.collections import User


def get_configured_admins():
    configured = [
        (
            "INITIAL_ADMIN",
            settings.initial_admin_email,
            settings.initial_admin_password,
            "admin",
            "Admin",
            "One",
        ),
        (
            "INITIAL_SUPERADMIN",
            settings.initial_superadmin_email,
            settings.initial_superadmin_password,
            "superadmin",
            "Super Admin",
            "One",
        ),
    ]

    admins = []
    seen_emails = set()

    for label, email, password, role, first_name, last_name in configured:
        if bool(email) != bool(password):
            raise RuntimeError(
                f"{label}: both email and password must be configured."
            )

        if not email:
            continue

        normalized_email = email.strip().lower()

        if not normalized_email or normalized_email in seen_emails:
            raise RuntimeError(f"{label}: invalid or duplicate email.")

        if len(password.encode("utf-8")) > 72:
            raise RuntimeError(f"{label}: password exceeds 72 UTF-8 bytes.")

        seen_emails.add(normalized_email)

        admins.append({
            "email": normalized_email,
            "password": password,
            "role": role,
            "f_name": first_name,
            "l_name": last_name,
        })

    if not admins:
        raise RuntimeError("No initial administrator is configured.")

    return admins


async def main():
    admins = get_configured_admins()
    await connect_db()

    try:
        async with SessionLocal() as db:
            for admin in admins:
                result = await db.execute(
                    select(User)
                    .where(User.email == admin["email"])
                    .with_for_update()
                )
                existing = result.scalar_one_or_none()

                if existing:
                    if (
                        existing.role == "superadmin"
                        and admin["role"] != "superadmin"
                    ):
                        raise RuntimeError(
                            "Refusing to demote an existing superadmin "
                            "through the initial-admin bootstrap."
                        )

                    existing.role = admin["role"]
                    existing.verified = True
                    existing.suspended = False
                    existing.password = hash_password(admin["password"])
                    print(f"Updated {admin['role']}: {admin['email']}")
                else:
                    db.add(User(
                        email=admin["email"],
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
                        suspended=False,
                        role=admin["role"],
                        referral_id=None,
                        referrer_id=None,
                    ))
                    print(f"Created {admin['role']}: {admin['email']}")

            await db.commit()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
