import os
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class BaseAppSettings(BaseSettings):
    # Base directory
    BASE_DIR: Path = Path(__file__).parent.parent

    # Email settings
    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "mailhog")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", 1025))
    EMAIL_HOST_USER: str = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD: str = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS: bool = os.getenv("EMAIL_USE_TLS", "False").lower() == "true"

    # MinIO settings
    MINIO_HOST: str = os.getenv("MINIO_HOST", "minio")
    MINIO_PORT: int = int(os.getenv("MINIO_PORT", 9000))
    MINIO_ROOT_USER: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    MINIO_ROOT_PASSWORD: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "cinema-storage")

    @property
    def MINIO_ENDPOINT(self) -> str:
        return f"http://{self.MINIO_HOST}:{self.MINIO_PORT}"

    model_config = ConfigDict(
        extra="allow"
    )


class Settings(BaseAppSettings):
    # Database settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "cinema_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "cinema_password")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5433))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "cinema_db")
    DB_ECHO_LOG: bool = os.getenv("DB_ECHO_LOG", "true").lower() == "true"
    COOKIE: bool = False # DEVELOP -> False. PROD -> True

    @property
    def database_url(self) -> str:
        """
        Get AsyncPG database URL.
        """
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )

    model_config = ConfigDict(
        env_file=(".env.prod", ".env", ".env.local"),
        extra="allow"
    )


class TestSettings(BaseAppSettings):
    # Test database settings
    POSTGRES_USER: str = "test_user"
    POSTGRES_PASSWORD: str = "test_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "test_db"
    DB_ECHO_LOG: bool = False

    @property
    def database_url(self) -> str:
        """
        Get AsyncPG database URL for tests.
        """
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )

    model_config = ConfigDict(
        extra="allow"
    )


# Create settings instance based on environment
settings = Settings()
