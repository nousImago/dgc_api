from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.database import DatabaseSettings
from config.email import EmailSettings
from config.jwt import JWTSettings
from config.line_notify import LineNotifySettings
from config.storage import S3Settings


class _AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "DGC API"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = Field(default_factory=list)
    UPLOAD_PATH: str = "./uploads"


class Settings:
    """Root settings — composes per-concern settings classes."""

    def __init__(self) -> None:
        app = _AppSettings()
        self.APP_NAME = app.APP_NAME
        self.DEBUG = app.DEBUG
        self.LOG_LEVEL = app.LOG_LEVEL
        self.CORS_ORIGINS = app.CORS_ORIGINS
        self.UPLOAD_PATH = app.UPLOAD_PATH

        self.database = DatabaseSettings()
        self.jwt = JWTSettings()
        self.line_notify = LineNotifySettings()
        self.email = EmailSettings()
        self.storage = S3Settings()


settings = Settings()
