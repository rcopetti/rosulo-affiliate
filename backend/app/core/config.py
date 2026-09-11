from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://rosulo:rosulo@localhost:5432/rosulo_affiliate"
    secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    sqs_queue_url: str | None = None
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"

    # Email (AWS SES)
    email_backend: str = "console"  # "ses" or "console"
    email_from: str | None = None
    ses_region: str = "us-east-1"
    frontend_url: str = "http://localhost:5173"

    # Encrypted affiliate document storage (S3-compatible)
    documents_s3_bucket: str | None = None
    documents_s3_region: str = "us-east-1"
    documents_encryption_key: str | None = None
    documents_max_bytes: int = 10 * 1024 * 1024


settings = Settings()
