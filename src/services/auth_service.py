import secrets
from datetime import datetime, timedelta

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
        # 1. Проверка email на уникальность
        existing_user = await self.db.scalar(
            select(UserModel).where(UserModel.email == data.email)
        )
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # 2. Хэширование пароля
        hashed_password = hash_password(data.password)

        # 3. Создание пользователя
        new_user = UserModel(
            email=data.email,
            _hashed_password=hashed_password,
            is_active=False,
            group_id=await self._get_default_user_group_id(),  # см. ниже
        )
        self.db.add(new_user)
        await self.db.flush()  # получим ID

        # 4. Генерация токена
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        activation = ActivationTokenModel(
            user_id=new_user.id,
            token=token,
            expires_at=expires_at,
        )
        self.db.add(activation)
        await self.db.commit()

        # 5. Отправка письма
        activation_link = f"http://localhost:8000/api/accounts/activate?token={token}"
        send_email_notification.delay(
            user_id=new_user.id,
            subject="Activate your account",
            message=f"Click to activate: {activation_link}",
        )

        return {"detail": "Activation email sent."}

    async def _get_default_user_group_id(self) -> int:
        # Возвращает id группы USER
        group = await self.db.scalar(
            select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
        )
        if not group:
            raise HTTPException(500, "Default user group not found")
        return group.id
