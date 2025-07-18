from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None


class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr]

    class Config:
        orm_mode = True


class UserLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"