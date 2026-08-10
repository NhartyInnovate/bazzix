from pydantic import BaseModel, EmailStr, Field, field_validator
import re

class UserCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        lower_pass = v.lower()
        common_passwords = [
            "password",
            "password123",
            "passwordpassword",
            "12345678",
            "123456789",
            "1234567890",
            "123456789012",
            "qwertyuiop",
            "qwerty123456",
            "iloveyou",
        ]
        if lower_pass in common_passwords:
            raise ValueError("This password is too common. Please choose a unique passphrase.")

        if re.match(r"^(.)\1+$", v):
            raise ValueError("Passwords cannot be a single repeating character.")

        sequential_patterns = [
            "12345678",
            "23456789",
            "98765432",
            "87654321",
            "abcdefgh",
            "hgfedcba",
            "qazwsxedc",
        ]
        for pattern in sequential_patterns:
            if pattern in lower_pass:
                raise ValueError("This password contains a common sequence. Please choose something more secure.")

        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str