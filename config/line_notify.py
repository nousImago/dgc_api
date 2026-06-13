from pydantic_settings import BaseSettings, SettingsConfigDict


class LineNotifySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LINE_NOTIFY_TOKEN: str = ""
    LINE_NOTIFY_URL: str = "https://notify-api.line.me/api/notify"
