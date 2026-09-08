from pydantic import BaseModel, Field, HttpUrl


ALLOWED_TEMPLATE_IDS = {
    "welcome",
    "verification",
    "deposit_approved",
    "withdrawal_approved",
    "suspension",
    "reinstatement",
}


class EmailCTA(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    url: HttpUrl


class SendEmailIn(BaseModel):
    userId: int = Field(gt=0)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    cta: EmailCTA | None = None
    templateId: str | None = Field(default=None, max_length=50)


class BroadcastEmailIn(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    cta: EmailCTA | None = None
    templateId: str | None = Field(default=None, max_length=50)
