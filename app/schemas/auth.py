from pydantic import BaseModel, EmailStr, Field, field_validator
from app.schemas.user import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=12, max_length=128)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)

class VerifyEmailRequest(BaseModel):
    token: str

class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=1)

    @field_validator('credential')
    @classmethod
    def validate_credential(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Credential cannot be empty.")
        return v.strip()
