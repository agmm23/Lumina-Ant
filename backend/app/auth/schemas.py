"""
Esquemas Pydantic para el módulo de autenticación.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str   # ID token devuelto por Google JS SDK


class UserConfigOut(BaseModel):
    language: str
    theme: str
    alert_preferences: str
    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    config: UserConfigOut
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UpdateConfigRequest(BaseModel):
    language: Optional[str] = None    # 'es' | 'en'
    theme: Optional[str] = None       # 'light' | 'dark'
    alert_preferences: Optional[str] = None  # JSON string
