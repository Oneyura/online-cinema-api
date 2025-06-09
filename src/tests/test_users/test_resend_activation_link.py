import pytest
from unittest.mock import AsyncMock, patch, Mock
from datetime import datetime, timezone, timedelta

from src.services.auth_service import AuthService
from src.database.models.accounts import UserModel, ActivationTokenModel


@pytest.mark.asyncio
@patch("src.services.auth_service.send_email_notification.delay")
async def test_resend_activation_email_user_not_found(mock_send_email):
    db = AsyncMock()
    db.scalar.return_value = None

    service = AuthService(db)

    result = await service.resend_activation_email("notfound@example.com")

    assert result["detail"] == "If the email is registered and not activated, an activation link has been sent."
    mock_send_email.assert_not_called()
    db.delete.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
@patch("src.services.auth_service.send_email_notification.delay")
async def test_resend_activation_email_user_already_active(mock_send_email):
    user = UserModel(id=1, email="active@example.com", is_active=True)
    db = AsyncMock()
    db.scalar.side_effect = [user]

    service = AuthService(db)

    result = await service.resend_activation_email(user.email)

    assert result["detail"] == "If the email is registered and not activated, an activation link has been sent."
    mock_send_email.assert_not_called()
    db.delete.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
@patch("src.services.auth_service.send_email_notification.delay")
async def test_resend_activation_email_success_with_old_token(mock_send_email):
    user = UserModel(id=1, email="inactive@example.com", is_active=False)
    old_token = ActivationTokenModel(
        id=10, user_id=user.id, token="oldtoken", expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )

    db = AsyncMock()
    db.scalar.side_effect = [user, old_token]

    db.delete = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()

    service = AuthService(db)

    result = await service.resend_activation_email(user.email)

    assert result["detail"] == "If the email is registered and not activated, an activation link has been sent."
    db.delete.assert_called_once_with(old_token)
    db.add.assert_called_once()
    db.commit.assert_called()
    mock_send_email.assert_called_once()

    called_args, called_kwargs = mock_send_email.call_args
    assert called_kwargs.get("user_id") == user.id
    assert "Activate your account - Resend" in called_kwargs.get("subject", "")
    assert "activate" in called_kwargs.get("message", "")


@pytest.mark.asyncio
@patch("src.services.auth_service.send_email_notification.delay")
async def test_resend_activation_email_success_without_old_token(mock_send_email):
    user = UserModel(id=2, email="inactive2@example.com", is_active=False)

    db = AsyncMock()
    db.scalar.side_effect = [user, None]

    db.delete = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()

    service = AuthService(db)

    result = await service.resend_activation_email(user.email)

    assert result["detail"] == "If the email is registered and not activated, an activation link has been sent."
    db.delete.assert_not_called()
    db.add.assert_called_once()
    db.commit.assert_called()
    mock_send_email.assert_called_once()
