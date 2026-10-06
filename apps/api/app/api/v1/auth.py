"""Auth router: register / login / refresh / logout."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import problem
from app.db.session import get_session
from app.schemas.auth import LoginIn, RefreshIn, RegisterIn
from app.services import auth as auth_service

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(body: RegisterIn, request: Request, session: AsyncSession = Depends(get_session)):  # type: ignore[arg-type]
    if len(body.password) < 8:
        return problem(request, 422, "Unprocessable", "password must be >= 8 chars")
    try:
        user = await auth_service.register(session, body.email, body.password)
    except ValueError:
        return problem(request, 409, "Conflict", "email already registered")
    access, refresh = await auth_service.issue_pair(session, user.id)
    return {"user": {"id": user.id, "email": user.email}, "access_token": access, "refresh_token": refresh}


@router.post("/login")
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(get_session)):  # type: ignore[arg-type]
    user = await auth_service.authenticate(session, body.email, body.password)
    if user is None:
        return problem(request, 401, "Unauthorized", "invalid credentials")
    access, refresh = await auth_service.issue_pair(session, user.id)
    return {"user": {"id": user.id, "email": user.email}, "access_token": access, "refresh_token": refresh}


@router.post("/refresh")
async def refresh(body: RefreshIn, request: Request, session: AsyncSession = Depends(get_session)):  # type: ignore[arg-type]
    pair = await auth_service.rotate_refresh(session, body.refresh_token)
    if pair is None:
        return problem(request, 401, "Unauthorized", "invalid refresh token")
    return {"access_token": pair[0], "refresh_token": pair[1]}


@router.post("/logout", status_code=204)
async def logout(body: RefreshIn, session: AsyncSession = Depends(get_session)):  # type: ignore[arg-type]
    await auth_service.revoke_refresh(session, body.refresh_token)
    return None
