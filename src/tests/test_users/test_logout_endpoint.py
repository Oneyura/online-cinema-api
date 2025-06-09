import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_logout_successful(async_client: AsyncClient, async_session: AsyncSession):
    token_value = "test_refresh_token"

    # Мокаем scalars().first() → токен найден
    mock_token = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = mock_token

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    with (
        patch.object(async_session, "execute", new_callable=AsyncMock, return_value=mock_result) as mock_execute,
        patch.object(async_session, "delete", new_callable=AsyncMock) as mock_delete,
        patch.object(async_session, "commit", new_callable=AsyncMock) as mock_commit,
    ):

        response = await async_client.post("/auth/logout", cookies={"refresh_token": token_value})

        assert response.status_code == 204
        mock_execute.assert_awaited_once()
        mock_delete.assert_awaited_once_with(mock_token)
        mock_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_without_cookie(async_client: AsyncClient, async_session: AsyncSession):
    with (
        patch.object(async_session, "execute", new_callable=AsyncMock) as mock_execute,
        patch.object(async_session, "commit", new_callable=AsyncMock) as mock_commit,
    ):

        response = await async_client.post("/auth/logout")  # Без refresh_token

        assert response.status_code == 204
        mock_execute.assert_not_called()
        mock_commit.assert_not_called()


@pytest.mark.asyncio
async def test_logout_token_not_found(async_client: AsyncClient, async_session: AsyncSession):
    token_value = "nonexistent_token"

    # scalars().first() → None
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    with (
        patch.object(async_session, "execute", new_callable=AsyncMock, return_value=mock_result) as mock_execute,
        patch.object(async_session, "delete", new_callable=AsyncMock) as mock_delete,
        patch.object(async_session, "commit", new_callable=AsyncMock) as mock_commit,
    ):

        response = await async_client.post("/auth/logout", cookies={"refresh_token": token_value})

        assert response.status_code == 204
        mock_execute.assert_awaited_once()
        mock_delete.assert_not_called()
        mock_commit.assert_not_called()
