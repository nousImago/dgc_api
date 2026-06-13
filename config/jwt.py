from pydantic_settings import BaseSettings, SettingsConfigDict


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    # Both token TTLs are expressed in minutes and used as a fallback
    # when the end-of-day cap below is disabled (mainly tests).
    JWT_ACCESS_TTL_MINUTES: int = 60
    JWT_REFRESH_TTL_MINUTES: int = 20160
    # Cap every token (access *and* refresh) at the next local midnight
    # in JWT_ACCESS_TIMEZONE. This forces an end-of-day auto-logout no
    # matter how recently the user was active or refreshed.
    JWT_ACCESS_END_OF_DAY: bool = True
    JWT_ACCESS_TIMEZONE: str = "Asia/Bangkok"
