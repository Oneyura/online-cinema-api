import os
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import BaseAppSettings, ProductionSettings, Settings, TestSettings
from src.database.models import UserModel
from src.exceptions.security import InvalidTokenError, TokenExpiredError
from src.notifications.emails import EmailSender
from src.notifications.interfaces import EmailSenderInterface
from src.security.interfaces import JWTAuthManagerInterface
from src.security.token_manager import JWTAuthManager
from src.storages.interfaces import S3StorageInterface
from src.storages.s3 import S3StorageClient

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_settings() -> BaseAppSettings:
    """Get application settings based on the current environment."""
    environment = os.getenv("ENVIRONMENT", "developing")
    if environment == "testing":
        return TestSettings()
    elif environment == "production":
        return ProductionSettings()
    return Settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from src.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


def get_token(token: str = Depends(oauth2_scheme)) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


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
        algorithm=settings.JWT_SIGNING_ALGORITHM,
    )


def get_email_sender(
    settings: BaseAppSettings = Depends(get_settings),
) -> EmailSenderInterface:
    """Get email sender instance."""
    return EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        sender_email=settings.EMAIL_FROM,
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


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserModel:
    """
    Get current authenticated user from JWT token.

    Args:
        token: JWT token from Authorization header
        db: Database session
        jwt_manager: JWT authentication manager

    Returns:
        UserModel: The authenticated user

    Raises:
        HTTPException: If token is invalid or user not found/inactive
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise credentials_exception
    except Exception:
        raise credentials_exception

    result = await db.execute(select(UserModel).filter(UserModel.id == user_id))
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_moderator(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.group != "moderator" or current_user.group != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Operation forbidden. Requires moderator role."
        )
    return current_user
