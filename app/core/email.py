from datetime import datetime, timezone
from html import escape

import resend

from app.core.config import settings


resend.api_key = settings.resend_api_key


async def send_otp_email(
    email: str,
    otp: str,
):
    company_name = settings.company_name
    safe_company_name = escape(company_name)
    safe_company_tagline = escape(settings.company_tagline)
    current_year = datetime.now(timezone.utc).year

    params: resend.Emails.SendParams = {
        "from": settings.from_email,
        "to": [email],
        "subject": f"Your {company_name} Verification Code",
        "html": f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_company_name} Verification</title>
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
                        {safe_company_name}
                    </div>

                    <div style="
                        margin-top:6px;
                        font-size:13px;
                        color:#9ca3af;
                    ">
                        {safe_company_tagline}
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
                        {safe_company_name} account.
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
                        © {current_year} {safe_company_name}. All rights reserved.
                    </p>
                </div>

            </div>

        </body>
        </html>
        """,
    }

    return await resend.Emails.send_async(params)








def render_admin_email(
    receiver_name: str,
    subject: str,
    body: str,
    cta_label: str | None = None,
    cta_url: str | None = None,
) -> str:
    current_year = datetime.now(timezone.utc).year
    safe_company_name = escape(settings.company_name)
    unsubscribe_target = (
        settings.unsubscribe_url
        or f"{settings.app_url.rstrip('/')}/unsubscribe"
    )
    safe_unsubscribe_url = escape(unsubscribe_target, quote=True)

    safe_receiver_name = escape(receiver_name or "Customer")
    safe_subject = escape(subject)
    safe_body = escape(body).replace("\n", "<br>")
    safe_cta_label = escape(cta_label) if cta_label else ""
    safe_cta_url = escape(cta_url) if cta_url else ""

    cta_block = ""

    if cta_label and cta_url:
        cta_block = f"""
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td style="padding:28px 32px 36px;" align="center">
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml"
                href="{safe_cta_url}"
                style="height:48px;v-text-anchor:middle;width:100%;"
                arcsize="16%"
                fillcolor="#1b2e4b"
                stroke="f">
                <center style="color:#ffffff;font-family:Arial,sans-serif;font-size:14px;font-weight:bold;">
                  {safe_cta_label}
                </center>
              </v:roundrect>
              <![endif]-->

              <!--[if !mso]><!-->
              <a
                href="{safe_cta_url}"
                style="
                  display:block;
                  background:#1b2e4b;
                  color:#ffffff;
                  font-size:14px;
                  font-weight:600;
                  text-decoration:none;
                  padding:14px 24px;
                  border-radius:8px;
                  text-align:center;
                  letter-spacing:.2px;
                ">
                {safe_cta_label}
              </a>
              <!--<![endif]-->
            </td>
          </tr>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_subject}</title>

  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    body {{
      background-color: #f5f6fa;
    }}
  </style>
</head>

<body style="
  background-color:#f5f6fa;
  padding:40px 16px;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
">

  <div style="
    display:none;
    max-height:0;
    overflow:hidden;
    font-size:1px;
    color:transparent;
  ">
    {safe_subject}
  </div>

  <table
    align="center"
    width="100%"
    cellpadding="0"
    cellspacing="0"
    role="presentation"
    style="max-width:460px;margin:0 auto;"
  >

    <tr>
      <td style="
        background:#ffffff;
        border-radius:12px;
        overflow:hidden;
      ">

        <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
          style="background:#1b2e4b;">
          <tr>
            <td style="padding:22px 28px;">
              <span style="
                font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                font-size:17px;
                color:#ffffff;
                letter-spacing:-.2px;
                font-weight:700;
              ">
                {safe_company_name}
              </span>
            </td>
          </tr>
        </table>

        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td style="padding:36px 32px 0;">

              <p style="
                font-size:14px;
                color:#4a4a4a;
                line-height:1.65;
                margin:0;
              ">
                Dear {safe_receiver_name},
              </p>

              <p style="
                margin:14px 0 0;
                font-size:14px;
                color:#4a4a4a;
                line-height:1.65;
              ">
                {safe_body}
              </p>

            </td>
          </tr>
        </table>

        {cta_block}

        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td style="padding:0 32px;">
              <div style="border-top:1px solid #ebe8e4;"></div>
            </td>
          </tr>

          <tr>
            <td style="padding:20px 32px 24px;">
              <p style="
                font-size:13px;
                color:#4a4a4a;
                line-height:1.5;
                margin:0;
              ">
                Thank you,<br>
                <span style="font-weight:600;color:#1e1e2d;">
                  The {safe_company_name} Team
                </span>
              </p>
            </td>
          </tr>
        </table>

      </td>
    </tr>

    <tr>
      <td style="padding:28px 4px 0;text-align:center;">

        <p style="
          font-size:11px;
          color:#b0b0b0;
          line-height:1.7;
          margin:0;
        ">
          &copy; {current_year} {safe_company_name}. All rights reserved.
        </p>

        <p style="
          font-size:11px;
          color:#b0b0b0;
          margin:6px 0 0;
        ">
          <a
            href="{safe_unsubscribe_url}"
            style="
              color:#b0b0b0;
              text-decoration:underline;
            ">
            Unsubscribe
          </a>
        </p>

      </td>
    </tr>

  </table>

</body>
</html>
"""


async def send_admin_email(
    email: str,
    subject: str,
    html: str,
):
    params: resend.Emails.SendParams = {
        "from": settings.from_email,
        "to": [email],
        "subject": subject,
        "html": html,
    }

    return await resend.Emails.send_async(params)
