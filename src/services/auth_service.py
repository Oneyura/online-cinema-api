import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from src.schemas.auth import UserRegistrationRequestSchema
from src.security.passwords import hash_password
from src.tasks import send_email_notification
from src.database.models.accounts import UserModel, UserGroupEnum, UserGroupModel, ActivationTokenModel


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, data: UserRegistrationRequestSchema) -> dict:
        existing_user = await self.db.scalar(
            select(UserModel).where(UserModel.email == data.email)
        )
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = hash_password(data.password)

        new_user = UserModel(
            email=data.email,
            _hashed_password=hashed_password,
            is_active=False,
            group_id=await self._get_default_user_group_id(),  # см. ниже
        )
        self.db.add(new_user)
        await self.db.flush()  # получим ID

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        activation = ActivationTokenModel(
            user_id=new_user.id,
            token=token,
            expires_at=expires_at,
        )
        self.db.add(activation)
        await self.db.commit()

        activation_link = f"http://localhost:8000/api/accounts/activate?token={token}"
        send_email_notification.delay(
            user_id=new_user.id,
            subject="Activate your account",
            message=f"Click to activate: {activation_link}",
        )

        return {"detail": "Activation email sent."}

    async def _get_default_user_group_id(self) -> int:
        group = await self.db.scalar(
            select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
        )
        if not group:
            raise HTTPException(500, "Default user group not found")
        return group.id

    async def activate_user_by_token(self, token: str) -> dict:
        stmt = select(ActivationTokenModel).where(ActivationTokenModel.token == token)
        activation_token = await self.db.scalar(stmt)

        if not activation_token:
            raise HTTPException(status_code=400, detail="Invalid activation token.")

        if activation_token.expires_at < datetime.now(timezone.utc):
            await self.db.delete(activation_token)
            await self.db.commit()
            raise HTTPException(status_code=400, detail="Activation token has expired.")

        user = await self.db.get(UserModel, activation_token.user_id)
        if not user:
            raise HTTPException(status_code=400, detail="User not found.")

        if user.is_active:
            raise HTTPException(status_code=400, detail="User is already active.")

        user.is_active = True
        await self.db.delete(activation_token)
        await self.db.commit()

        login_link = "http://localhost:8000/login"
        send_email_notification.delay(
            user_id=user.id,
            subject="Account Activated Successfully",
            message=f"Your account has been activated. You can login here: {login_link}"
        )

        return {"detail": "Account activated successfully."}

    async def resend_activation_email(self, email: str) -> dict:
        """
        Resend activation email.

        If a user with the given email exists and is not activated,
        deletes the old token, creates a new one, and sends an email.
        If the user is not found or already activated, returns a neutral response.
        """
        stmt = select(UserModel).where(UserModel.email == email)
        user = await self.db.scalar(stmt)

        # Do not disclose information if user is not found or already activated
        if not user or user.is_active:
            return {"detail": "If the email is registered and not activated, an activation link has been sent."}

        # Delete old token if exists
        old_token_stmt = select(ActivationTokenModel).where(ActivationTokenModel.user_id == user.id)
        old_token = await self.db.scalar(old_token_stmt)
        if old_token:
            await self.db.delete(old_token)
            await self.db.commit()

        # Create a new token with 24-hour TTL
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        new_token = ActivationTokenModel(
            user_id=user.id,
            token=token,
            expires_at=expires_at
        )
        self.db.add(new_token)
        await self.db.commit()

        # Send email via Celery
        activation_link = f"http://localhost:8000/accounts/activate?token={token}"
        send_email_notification.delay(
            user_id=user.id,
            subject="Activate your account - Resend",
            message=f"Please activate your account by clicking the link: {activation_link}"
        )

        return {"detail": "If the email is registered and not activated, an activation link has been sent."}
