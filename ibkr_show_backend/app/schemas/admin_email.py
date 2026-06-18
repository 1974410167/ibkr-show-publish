from pydantic import BaseModel


class EmailSettingsResponse(BaseModel):
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password_masked: str
    has_smtp_password: bool
    smtp_use_ssl: bool
    smtp_use_starttls: bool
    email_from: str
    email_to: str
    subject_prefix: str
    site_base_url: str
    config_file: str
    daily_review_email_enabled: bool
    daily_review_email_to: str
    daily_review_subject_prefix: str
    daily_snapshot_email_enabled: bool
    daily_snapshot_email_to: str
    daily_snapshot_subject_prefix: str
    portfolio_action_alerts_email_enabled: bool
    portfolio_action_alerts_email_to: str
    portfolio_action_alerts_subject_prefix: str


class EmailSettingsUpdateRequest(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str | None = None
    smtp_use_ssl: bool
    smtp_use_starttls: bool
    email_from: str
    daily_review_email_enabled: bool
    daily_review_email_to: str
    daily_review_subject_prefix: str | None = None
    site_base_url: str | None = None
    daily_snapshot_email_enabled: bool
    daily_snapshot_email_to: str
    daily_snapshot_subject_prefix: str | None = None
    portfolio_action_alerts_email_enabled: bool = False
    portfolio_action_alerts_email_to: str = ""
    portfolio_action_alerts_subject_prefix: str | None = None


class EmailSettingsMutationResponse(BaseModel):
    settings: EmailSettingsResponse
    message: str


class EmailTestRequest(BaseModel):
    subject: str | None = None
    message: str | None = None


class EmailTestResponse(BaseModel):
    success: bool
    message: str
    sent_to: list[str]
    sent_at: str


class EmailSendLatestResponse(BaseModel):
    success: bool
    sent: bool
    report_date: str | None
    message: str
    task_id: str | None = None
    status: str | None = None


class EmailSendLatestDailyReviewRequest(BaseModel):
    force_refresh: bool = False
    regenerate_if_legacy: bool = True
