import asyncio
from app.core.database import connect_db, close_db, get_db
from app.core.security import hash_password


ADMINS = [
    {
        "email": "admin@iconinvest.local",
        "password": "Admin12345678!",
        "f_name": "Admin",
        "l_name": "One",
    },
    {
        "email": "admin2@iconinvest.local",
        "password": "Admin23456789!",
        "f_name": "Admin",
        "l_name": "Two",
    },
]


async def main():
    await connect_db()
    db = get_db()

    for admin in ADMINS:
        email = admin["email"].lower()

        existing = await db.users.find_one({"email": email})

        if existing:
            await db.users.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "role": "admin",
                        "verified": True,
                    }
                },
            )
            print(f"Admin already exists/updated: {email}")
        else:
            user = {
                "email": email,
                "password": hash_password(admin["password"]),
                "f_name": admin["f_name"],
                "l_name": admin["l_name"],
                "phone": "",
                "country": "Nigeria",
                "balance": 0,
                "profit": 0,
                "depositBalance": 0,
                "referralBalance": 0,
                "withdrawBalance": 0,
                "investBalance": 0,
                "currency": "usd",
                "verified": True,
                "role": "admin",
                "referralId": "",
                "referrerId": "",
            }

            result = await db.users.insert_one(user)

            print(f"Admin created: {email}")
            print(f"ID: {result.inserted_id}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())