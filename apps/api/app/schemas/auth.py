"""Pydantic v2 schemas for auth."""

from pydantic import BaseModel, EmailStr


class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class GoogleIn(BaseModel):
    id_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
