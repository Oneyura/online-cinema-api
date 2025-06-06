import os
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import BaseAppSettings, Settings, TestSettings
from src.notifications.emails import EmailSender
from src.notifications.interfaces import EmailSenderInterface
from src.security.token_manager import JWTAuthManager
from src.storages.interfaces import S3StorageInterface
from src.storages.s3 import S3StorageClient
from src.security.interfaces import JWTAuthManagerInterface


def get_settings() -> BaseAppSettings:
    """Get application settings based on the current environment."""
    environment = os.getenv("ENVIRONMENT", "developing")
    if environment == "testing":
        return TestSettings()
    return Settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from src.database.session import get_async_session
    async with get_async_session() as session:
        yield session


def get_email_sender(
    settings: BaseAppSettings = Depends(get_settings),
) -> EmailSenderInterface:
    """Get email sender instance."""
    return EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        email=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        template_dir="src/templates/email",
        activation_email_template_name="activation.html",
        activation_complete_email_template_name="activation_complete.html",
        password_email_template_name="password_reset.html",
        password_complete_email_template_name="password_reset_complete.html",
    )


def get_minio_client(
    settings: BaseAppSettings = Depends(get_settings),
) -> S3StorageInterface:
    """Get MinIO client instance."""
    return S3StorageClient(
        endpoint_url=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        bucket_name=settings.MINIO_BUCKET_NAME,
    )

def get_jwt_auth_manager(settings: BaseAppSettings = Depends(get_settings)) -> JWTAuthManagerInterface:
    """
    Create and return a JWT authentication manager instance.

    This function uses the provided application settings to instantiate a JWTAuthManager, which implements
    the JWTAuthManagerInterface. The manager is configured with secret keys for access and refresh tokens
    as well as the JWT signing algorithm specified in the settings.

    Args:
        settings (BaseAppSettings, optional): The application settings instance.
        Defaults to the output of get_settings().

    Returns:
        JWTAuthManagerInterface: An instance of JWTAuthManager configured with
        the appropriate secret keys and algorithm.
    """
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )
