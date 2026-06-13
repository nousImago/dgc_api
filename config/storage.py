from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Settings(BaseSettings):
    """S3-compatible object storage settings.

    Env var names follow the MINIO_* convention used by the Helm chart
    (.chart/values/api/values-api-*.yaml). The client speaks the S3
    protocol, so any S3-compatible target works — MinIO, R2, AWS S3.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_REGION: str = "us-east-1"
    MINIO_BUCKET_NAME: str = "dgc-uploads"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"

    MINIO_PUBLIC_BASE_URL: str = ""
    MINIO_PRESIGNED_URL_TTL_SECONDS: int = 3600

    @field_validator("MINIO_ENDPOINT", mode="after")
    @classmethod
    def _normalize_endpoint(cls, v: str) -> str:
        if not v or v.startswith(("http://", "https://")):
            return v
        # Bare hostname (e.g. storage-hq.postway.co.th): assume https for public
        # hosts, http for localhost / explicit-port targets.
        first = v.split("/", 1)[0]
        if first.startswith(("localhost", "127.0.0.1")) or ":" in first:
            return f"http://{v}"
        return f"https://{v}"
