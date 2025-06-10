from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.params import Cookie
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.config.dependencies import BaseAppSettings, get_db, get_jwt_auth_manager, get_settings
from src.config.settings import settings
from src.database.models.accounts import (
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserGroupEnum,
    UserGroupModel,
    UserModel,
)
from src.database.session import get_async_session
from src.exceptions.security import BaseSecurityError
from src.schemas.auth import (
    MessageResponseSchema,
    PasswordResetCompleteRequestSchema,
    PasswordResetRequestSchema,
    ResendActivationRequestSchema,
    TokenRefreshRequestSchema,
    TokenRefreshResponseSchema,
    UserActivationRequestSchema,
    UserLoginRequestSchema,
    UserLoginResponseSchema,
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema,
)
from src.security.interfaces import JWTAuthManagerInterface
from src.services.auth_service import AuthService
from src.tasks import send_activation_email, send_activation_complete_email, send_password_reset_email, send_password_reset_complete_email

accounts_router = APIRouter()


@accounts_router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    summary="User Registration",
    description="Register a new user with an email and password.",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "description": "Conflict - User with this email already exists.",
            "content": {
                "application/json": {"example": {"detail": "A user with this email test@example.com already exists."}}
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred during user creation.",
            "content": {"application/json": {"example": {"detail": "An error occurred during user creation."}}},
        },
    },
)
async def register_user(
    user_data: UserRegistrationRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> UserRegistrationResponseSchema:
    """
    Endpoint for user registration.

    Registers a new user, hashes their password, and assigns them to the default user group.
    If a user with the same email already exists, an HTTP 409 error is raised.
    In case of any unexpected issues during the creation process, an HTTP 500 error is returned.

    Args:
        user_data (UserRegistrationRequestSchema): The registration details including email and password.
        db (AsyncSession): The asynchronous database session.

    Returns:
        UserRegistrationResponseSchema: The newly created user's details.

    Raises:
        HTTPException:
            - 409 Conflict if a user with the same email exists.
            - 500 Internal Server Error if an error occurs during user creation.
    """
    stmt = select(UserModel).where(UserModel.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"A user with this email {user_data.email} already exists."
        )

    stmt = select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
    result = await db.execute(stmt)
    user_group = result.scalars().first()
    if not user_group:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Default user group not found.")

    try:
        new_user = UserModel.create(
            email=str(user_data.email),
            raw_password=user_data.password,
            group_id=user_group.id,
        )
        db.add(new_user)
        await db.flush()

        activation_token = ActivationTokenModel(user_id=new_user.id)
        db.add(activation_token)

        await db.commit()
        await db.refresh(new_user)
        
        # Send activation email
        send_activation_email.delay(
            user_id=new_user.id,
            activation_token=activation_token.token,
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during user creation."
        ) from e
    else:
        return UserRegistrationResponseSchema.model_validate(new_user)


@accounts_router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    summary="Activate User Account",
    description="Activate a user's account using their email and activation token.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The activation token is invalid or expired, "
            "or the user account is already active.",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_token": {
                            "summary": "Invalid Token",
                            "value": {"detail": "Invalid or expired activation token."},
                        },
                        "already_active": {
                            "summary": "Account Already Active",
                            "value": {"detail": "User account is already active."},
                        },
                    }
                }
            },
        },
    },
)
async def activate_account(
    activation_data: UserActivationRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    """
    Endpoint to activate a user's account.

    This endpoint verifies the activation token for a user by checking that the token record exists
    and that it has not expired. If the token is valid and the user's account is not already active,
    the user's account is activated and the activation token is deleted. If the token is invalid, expired,
    or if the account is already active, an HTTP 400 error is raised.

    Args:
        activation_data (UserActivationRequestSchema): Contains the user's email and activation token.
        db (AsyncSession): The asynchronous database session.

    Returns:
        MessageResponseSchema: A response message confirming successful activation.

    Raises:
        HTTPException:
            - 400 Bad Request if the activation token is invalid or expired.
            - 400 Bad Request if the user account is already active.
    """
    stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .join(UserModel)
        .where(UserModel.email == activation_data.email, ActivationTokenModel.token == activation_data.token)
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)
    if not token_record or cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc) < now_utc:
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired activation token.")

    user = token_record.user
    if user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is already active.")

    user.is_active = True
    await db.delete(token_record)
    await db.commit()

    # Send activation complete email
    send_activation_complete_email.delay(user_id=user.id)

    return MessageResponseSchema(message="User account activated successfully.")


@accounts_router.post(
    "/password-reset/request/",
    response_model=MessageResponseSchema,
    summary="Request Password Reset Token",
    description=(
        "Allows a user to request a password reset token. If the user exists and is active, "
        "a new token will be generated and any existing tokens will be invalidated."
    ),
    status_code=status.HTTP_200_OK,
)
async def request_password_reset_token(
    data: PasswordResetRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    """
    Endpoint to request a password reset token.

    If the user exists and is active, invalidates any existing password reset tokens and generates a new one.
    Always responds with a success message to avoid leaking user information.

    Args:
        data (PasswordResetRequestSchema): The request data containing the user's email.
        db (AsyncSession): The asynchronous database session.

    Returns:
        MessageResponseSchema: A success message indicating that instructions will be sent.
    """
    stmt = select(UserModel).filter_by(email=data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.is_active:
        return MessageResponseSchema(message="If you are registered, you will receive an email with instructions.")

    await db.execute(delete(PasswordResetTokenModel).where(PasswordResetTokenModel.user_id == user.id))

    reset_token = PasswordResetTokenModel(user_id=cast(int, user.id))
    db.add(reset_token)
    await db.commit()

    # Send password reset email
    send_password_reset_email.delay(
        user_id=user.id,
        reset_token=reset_token.token,
    )

    return MessageResponseSchema(message="If you are registered, you will receive an email with instructions.")


@accounts_router.post(
    "/reset-password/complete/",
    response_model=MessageResponseSchema,
    summary="Reset User Password",
    description="Reset a user's password if a valid token is provided.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": (
                "Bad Request - The provided email or token is invalid, "
                "the token has expired, or the user account is not active."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_email_or_token": {
                            "summary": "Invalid Email or Token",
                            "value": {"detail": "Invalid email or token."},
                        },
                        "expired_token": {"summary": "Expired Token", "value": {"detail": "Invalid email or token."}},
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred while resetting the password.",
            "content": {"application/json": {"example": {"detail": "An error occurred while resetting the password."}}},
        },
    },
)
async def reset_password(
    data: PasswordResetCompleteRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    """
    Endpoint for resetting a user's password.

    Validates the token and updates the user's password if the token is valid and not expired.
    Deletes the token after a successful password reset.

    Args:
        data (PasswordResetCompleteRequestSchema): The request data containing the user's email,
         token, and new password.
        db (AsyncSession): The asynchronous database session.

    Returns:
        MessageResponseSchema: A response message indicating successful password reset.

    Raises:
        HTTPException:
            - 400 Bad Request if the email or token is invalid, or the token has expired.
            - 500 Internal Server Error if an error occurs during the password reset process.
    """
    stmt = select(UserModel).filter_by(email=data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or token.")

    stmt = select(PasswordResetTokenModel).filter_by(user_id=user.id)
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    if not token_record or token_record.token != data.token:
        if token_record:
            await db.run_sync(lambda s: s.delete(token_record))
            await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or token.")

    expires_at = cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.run_sync(lambda s: s.delete(token_record))
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email or token.")

    try:
        user.password = data.password
        await db.run_sync(lambda s: s.delete(token_record))
        await db.commit()
        
        # Send password reset complete email
        send_password_reset_complete_email.delay(user.id)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while resetting the password."
        )

    return MessageResponseSchema(message="Password reset successfully.")


@accounts_router.post(
    "/login/",
    response_model=UserLoginResponseSchema,
    summary="User Login",
    description="Authenticate a user and return access and refresh tokens.",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {
            "description": "Unauthorized - Invalid email or password.",
            "content": {"application/json": {"example": {"detail": "Invalid email or password."}}},
        },
        403: {
            "description": "Forbidden - User account is not activated.",
            "content": {"application/json": {"example": {"detail": "User account is not activated."}}},
        },
        500: {
            "description": "Internal Server Error - An error occurred while processing the request.",
            "content": {"application/json": {"example": {"detail": "An error occurred while processing the request."}}},
        },
    },
)
async def login_user(
    login_data: UserLoginRequestSchema,
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserLoginResponseSchema:
    """
    Endpoint for user login.

    Authenticates a user using their email and password.
    If authentication is successful, creates a new refresh token and returns both access and refresh tokens.

    Args:
        login_data (UserLoginRequestSchema): The login credentials.
        db (AsyncSession): The asynchronous database session.
        settings (BaseAppSettings): The application settings.
        jwt_manager (JWTAuthManagerInterface): The JWT authentication manager.

    Returns:
        UserLoginResponseSchema: A response containing the access and refresh tokens.

    Raises:
        HTTPException:
            - 401 Unauthorized if the email or password is invalid.
            - 403 Forbidden if the user account is not activated.
            - 500 Internal Server Error if an error occurs during token creation.
    """
    stmt = select(UserModel).filter_by(email=login_data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user or not user.verify_password(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )

    jwt_refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    try:
        refresh_token = RefreshTokenModel.create(
            user_id=user.id, days_valid=settings.LOGIN_TIME_DAYS, token=jwt_refresh_token
        )
        db.add(refresh_token)
        await db.flush()
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        )

    jwt_access_token = jwt_manager.create_access_token({"user_id": user.id})
    return UserLoginResponseSchema(
        access_token=jwt_access_token,
        refresh_token=jwt_refresh_token,
    )


@accounts_router.post(
    "/refresh/",
    response_model=TokenRefreshResponseSchema,
    summary="Refresh Access Token",
    description="Refresh the access token using a valid refresh token.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The provided refresh token is invalid or expired.",
            "content": {"application/json": {"example": {"detail": "Token has expired."}}},
        },
        401: {
            "description": "Unauthorized - Refresh token not found.",
            "content": {"application/json": {"example": {"detail": "Refresh token not found."}}},
        },
        404: {
            "description": "Not Found - The user associated with the token does not exist.",
            "content": {"application/json": {"example": {"detail": "User not found."}}},
        },
    },
)
async def refresh_access_token(
    token_data: TokenRefreshRequestSchema,
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> TokenRefreshResponseSchema:
    """
    Endpoint to refresh an access token.

    Validates the provided refresh token, extracts the user ID from it, and issues
    a new access token. If the token is invalid or expired, an error is returned.

    Args:
        token_data (TokenRefreshRequestSchema): Contains the refresh token.
        db (AsyncSession): The asynchronous database session.
        jwt_manager (JWTAuthManagerInterface): JWT authentication manager.

    Returns:
        TokenRefreshResponseSchema: A new access token.

    Raises:
        HTTPException:
            - 400 Bad Request if the token is invalid or expired.
            - 401 Unauthorized if the refresh token is not found.
            - 404 Not Found if the user associated with the token does not exist.
    """
    try:
        decoded_token = jwt_manager.decode_refresh_token(token_data.refresh_token)
        user_id = decoded_token.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    stmt = select(RefreshTokenModel).filter_by(token=token_data.refresh_token)
    result = await db.execute(stmt)
    refresh_token_record = result.scalars().first()
    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    stmt = select(UserModel).filter_by(id=user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    new_access_token = jwt_manager.create_access_token({"user_id": user_id})

    return TokenRefreshResponseSchema(access_token=new_access_token)


@accounts_router.post(
    "/resend-activation/",
    response_model=MessageResponseSchema,
    summary="Resend Activation Email",
    description="Send a new activation link to the user's email if the account is not activated.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Activation email sent or user already activated.",
            "content": {
                "application/json": {
                    "example": {
                        "message": "If the email is registered and not activated, an activation link has been sent."
                    }
                }
            },
        },
        422: {
            "description": "Validation Error - Invalid email format.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "email"],
                                "msg": "value is not a valid email address",
                                "type": "value_error.email",
                            }
                        ]
                    }
                }
            },
        },
    },
)
async def resend_activation_email(
    data: ResendActivationRequestSchema,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    """
    Endpoint to resend the activation email to a user.

    If the user with the provided email exists and is not activated,
    a new activation token is generated and an activation email is sent.
    The response is neutral to avoid disclosing whether the email is registered.

    Args:
        data (ResendActivationRequestSchema): Contains the user's email.
        db (AsyncSession): The asynchronous database session.

    Returns:
        MessageResponseSchema: A message indicating that the activation email has been sent.
    """
    service = AuthService(db)
    result = await service.resend_activation_email(data.email)
    return MessageResponseSchema(**result)


@accounts_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="User Logout",
    description=(
        "Logs out the user by deleting the refresh"
        " token from the database and clearing the refresh token cookie.\n\n"
        "If the refresh token cookie is missing, the endpoint returns"
        " 204 No Content assuming the user is already logged out.\n\n"
        "If an error occurs during token deletion, the endpoint"
        " still returns a successful response to avoid breaking the logout flow."
    ),
    tags=["Authentication"],
)
async def logout_user(
    response: Response, refresh_token: str | None = Cookie(default=None), db: AsyncSession = Depends(get_async_session)
):
    if refresh_token is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    result = await db.execute(select(RefreshTokenModel).where(RefreshTokenModel.token == refresh_token))
    token_obj = result.scalars().first()

    if token_obj:
        await db.delete(token_obj)
        await db.commit()

    response.delete_cookie(
        key="refresh_token",
        path="/",
        httponly=True,
        secure=settings.COOKIE,
        samesite="lax",
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@accounts_router.get(
    "/activate",
    response_model=MessageResponseSchema,
    summary="Activate User Account via Email Link",
    description="Activate a user's account using the activation token from email link.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The activation token is invalid or expired, "
            "or the user account is already active.",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_token": {
                            "summary": "Invalid Token",
                            "value": {"detail": "Invalid or expired activation token."},
                        },
                        "already_active": {
                            "summary": "Account Already Active",
                            "value": {"detail": "User account is already active."},
                        },
                    }
                }
            },
        },
    },
)
async def activate_account_via_link(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    """
    Endpoint to activate a user's account via email link.
    
    This is a GET endpoint that accepts the activation token as a query parameter,
    making it compatible with email links. It performs the same logic as the POST
    activate endpoint but is more user-friendly for email activation workflows.

    Args:
        token (str): The activation token from the email link.
        db (AsyncSession): The asynchronous database session.

    Returns:
        MessageResponseSchema: A response message confirming successful activation.

    Raises:
        HTTPException:
            - 400 Bad Request if the activation token is invalid or expired.
            - 400 Bad Request if the user account is already active.
    """
    # Find the token in the database
    stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .where(ActivationTokenModel.token == token)
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)
    if not token_record or cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc) < now_utc:
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired activation token.")

    user = token_record.user
    if user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is already active.")

    user.is_active = True
    await db.delete(token_record)
    
    try:
        await db.commit()
        
        # Send activation complete email
        send_activation_complete_email.delay(user.id)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="An error occurred during account activation."
        )

    return MessageResponseSchema(message="Your account has been successfully activated!")


@accounts_router.get(
    "/password-reset/confirm",
    summary="Password Reset Confirmation Form",
    description="Display a password reset form for the user to enter their new password.",
    responses={
        200: {
            "description": "Password reset form displayed",
            "content": {"text/html": {"example": "<html>...</html>"}},
        },
        400: {
            "description": "Invalid or expired token",
            "content": {"text/html": {"example": "<html>Error: Invalid token</html>"}},
        },
    },
)
async def password_reset_form(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Display a password reset form when user clicks the link in their email.
    
    This endpoint validates the token and shows an HTML form for the user
    to enter their new password. The form submits to the complete endpoint.

    Args:
        token (str): The password reset token from the email link.
        db (AsyncSession): The asynchronous database session.

    Returns:
        HTMLResponse: An HTML form for password reset or error page.
    """
    from fastapi.responses import HTMLResponse
    
    # Validate token exists and is not expired
    stmt = (
        select(PasswordResetTokenModel)
        .options(joinedload(PasswordResetTokenModel.user))
        .where(PasswordResetTokenModel.token == token)
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    if not token_record:
        error_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Invalid Token</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #f4f4f4; }
                .container { max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .error { color: #d32f2f; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="error">Invalid or Expired Token</h2>
                <p>The password reset token is invalid or has expired.</p>
                <p>Please request a new password reset link.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)

    # Check if token is expired
    expires_at = cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        # Clean up expired token
        await db.delete(token_record)
        await db.commit()
        
        error_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Expired Token</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #f4f4f4; }
                .container { max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .error { color: #d32f2f; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="error">Token Expired</h2>
                <p>The password reset token has expired.</p>
                <p>Please request a new password reset link.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)

    user = token_record.user
    
    # Generate password reset form
    form_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Your Password</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                background-color: #f4f4f4; 
                margin: 0; 
                padding: 50px 20px; 
            }}
            .container {{ 
                max-width: 500px; 
                margin: 0 auto; 
                background: white; 
                padding: 30px; 
                border-radius: 8px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            }}
            .form-group {{ 
                margin-bottom: 20px; 
            }}
            label {{ 
                display: block; 
                margin-bottom: 5px; 
                font-weight: bold; 
                color: #333; 
            }}
            input[type="password"], input[type="email"] {{ 
                width: 100%; 
                padding: 12px; 
                border: 1px solid #ddd; 
                border-radius: 4px; 
                font-size: 16px; 
                box-sizing: border-box;
            }}
            button {{ 
                background-color: #FF9800; 
                color: white; 
                padding: 12px 24px; 
                border: none; 
                border-radius: 4px; 
                font-size: 16px; 
                cursor: pointer; 
                width: 100%; 
            }}
            button:hover {{ 
                background-color: #F57C00; 
            }}
            .header {{ 
                color: #FF9800; 
                text-align: center; 
                margin-bottom: 20px; 
            }}
            .info {{ 
                color: #666; 
                margin-bottom: 20px; 
            }}
            .error {{ 
                color: #d32f2f; 
                margin-bottom: 10px; 
                display: none; 
            }}
            .success {{ 
                color: #4CAF50; 
                margin-bottom: 10px; 
                display: none; 
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2 class="header">🔐 Reset Your Password</h2>
            <p class="info">Enter your new password for: <strong>{user.email}</strong></p>
            
            <div id="error-message" class="error"></div>
            <div id="success-message" class="success"></div>
            
            <form id="resetForm">
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" value="{user.email}" readonly>
                </div>
                
                <div class="form-group">
                    <label for="password">New Password:</label>
                    <input type="password" id="password" name="password" required 
                           minlength="8" placeholder="Enter your new password">
                </div>
                
                <div class="form-group">
                    <label for="confirmPassword">Confirm Password:</label>
                    <input type="password" id="confirmPassword" name="confirmPassword" required 
                           minlength="8" placeholder="Confirm your new password">
                </div>
                
                <input type="hidden" id="token" name="token" value="{token}">
                
                <button type="submit">Reset Password</button>
            </form>
        </div>
        
        <script>
            document.getElementById('resetForm').addEventListener('submit', async function(e) {{
                e.preventDefault();
                
                const password = document.getElementById('password').value;
                const confirmPassword = document.getElementById('confirmPassword').value;
                const email = document.getElementById('email').value;
                const token = document.getElementById('token').value;
                
                const errorDiv = document.getElementById('error-message');
                const successDiv = document.getElementById('success-message');
                
                // Clear previous messages
                errorDiv.style.display = 'none';
                successDiv.style.display = 'none';
                
                // Validate passwords match
                if (password !== confirmPassword) {{
                    errorDiv.textContent = 'Passwords do not match.';
                    errorDiv.style.display = 'block';
                    return;
                }}
                
                // Validate password strength
                if (password.length < 8) {{
                    errorDiv.textContent = 'Password must be at least 8 characters long.';
                    errorDiv.style.display = 'block';
                    return;
                }}
                
                try {{
                    const response = await fetch('/api/accounts/reset-password/complete/', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{
                            email: email,
                            password: password,
                            token: token
                        }})
                    }});
                    
                    const result = await response.json();
                    
                    if (response.ok) {{
                        successDiv.textContent = result.message || 'Password reset successfully!';
                        successDiv.style.display = 'block';
                        
                        // Disable form after success
                        document.getElementById('resetForm').style.display = 'none';
                        
                        // Show login link
                        const loginLink = document.createElement('p');
                        loginLink.innerHTML = '<a href="/api/accounts/login/" style="color: #FF9800;">You can now login with your new password</a>';
                        successDiv.appendChild(loginLink);
                    }} else {{
                        errorDiv.textContent = result.detail || 'An error occurred. Please try again.';
                        errorDiv.style.display = 'block';
                    }}
                }} catch (error) {{
                    errorDiv.textContent = 'Network error. Please try again.';
                    errorDiv.style.display = 'block';
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=form_html)
