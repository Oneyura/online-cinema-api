from pydantic import BaseModel, EmailStr, constr, Field, ConfigDict


class UserRegistrationSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "user@example.com", "password": "VerySecret123!"}}
    )

    email: EmailStr
    password: constr(min_length=8, max_length=128) = Field(..., description="Strong password")


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str


class TokenResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
