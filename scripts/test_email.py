import asyncio

from app.core.email import send_otp_email


async def main():
    result = await send_otp_email(
        "dkzy17@gmail.com",
        "123456",
    )

    print("EMAIL SENT")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())