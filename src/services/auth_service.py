from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.accounts import UserModel, ActivationTokenModel
from src.schemas.auth import UserRegistrationSchema
from src.database.validators import accounts as validators


class AuthService:
    @staticmethod
    async def register_user(data: UserRegistrationSchema, session: AsyncSession) -> UserModel:
        validators.validate_email(data.email)

        user = UserModel.create(
            email=data.email,
            raw_password=data.password,
            group_id=1
        )

        session.add(user)
        await session.flush()

        activation_token = ActivationTokenModel(user_id=user.id)
        session.add(activation_token)

        await session.commit()
        await session.refresh(user)

        return user
