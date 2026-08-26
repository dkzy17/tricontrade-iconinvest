import resend

from app.core.config import settings


resend.api_key = settings.resend_api_key


async def send_otp_email(
    email: str,
    otp: str,
):
    params: resend.Emails.SendParams = {
        "from": settings.from_email,
        "to": [email],
        "subject": "Your TriconTrade Verification Code",
        "html": f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TriconTrade Verification</title>
        </head>

        <body style="
            margin:0;
            padding:0;
            background:#f4f6f8;
            font-family:Arial, Helvetica, sans-serif;
            color:#1f2937;
        ">

            <div style="
                max-width:520px;
                margin:40px auto;
                background:#ffffff;
                border-radius:16px;
                overflow:hidden;
                box-shadow:0 4px 20px rgba(0,0,0,0.08);
            ">

                <div style="
                    background:#111827;
                    padding:28px 30px;
                    text-align:center;
                ">
                    <div style="
                        font-size:28px;
                        font-weight:700;
                        color:#ffffff;
                        letter-spacing:1px;
                    ">
                        TriconTrade
                    </div>

                    <div style="
                        margin-top:6px;
                        font-size:13px;
                        color:#9ca3af;
                    ">
                        Secure Trading & Investment
                    </div>
                </div>

                <div style="padding:36px 30px;">

                    <h2 style="
                        margin:0 0 16px;
                        font-size:24px;
                        color:#111827;
                    ">
                        Verify Your Email
                    </h2>

                    <p style="
                        margin:0 0 20px;
                        font-size:16px;
                        line-height:1.6;
                        color:#4b5563;
                    ">
                        Use the verification code below to confirm your
                        TriconTrade account.
                    </p>

                    <div style="
                        margin:28px 0;
                        padding:22px;
                        background:#f3f4f6;
                        border-radius:12px;
                        text-align:center;
                    ">
                        <div style="
                            font-size:13px;
                            color:#6b7280;
                            margin-bottom:10px;
                            text-transform:uppercase;
                            letter-spacing:1px;
                        ">
                            Verification Code
                        </div>

                        <div style="
                            font-size:36px;
                            font-weight:700;
                            letter-spacing:10px;
                            color:#111827;
                        ">
                            {otp}
                        </div>
                    </div>

                    <p style="
                        margin:0 0 14px;
                        font-size:14px;
                        line-height:1.6;
                        color:#6b7280;
                    ">
                        This code will expire in 10 minutes.
                    </p>

                    <p style="
                        margin:0;
                        font-size:14px;
                        line-height:1.6;
                        color:#6b7280;
                    ">
                        If you did not request this code, you can safely
                        ignore this email.
                    </p>

                </div>

                <div style="
                    padding:20px 30px;
                    background:#f9fafb;
                    border-top:1px solid #e5e7eb;
                    text-align:center;
                ">
                    <p style="
                        margin:0;
                        font-size:12px;
                        color:#9ca3af;
                    ">
                        © 2026 TriconTrade. All rights reserved.
                    </p>
                </div>

            </div>

        </body>
        </html>
        """,
    }

    return await resend.Emails.send_async(params)