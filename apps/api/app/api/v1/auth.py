"""Auth router: register / login / refresh / logout / google."""

from fastapi import APIRouter, Depends, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import problem
from app.db.session import get_session
from app.schemas.auth import GoogleIn, LoginIn, RefreshIn, RegisterIn
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


@router.post("/google")
async def google(body: GoogleIn, request: Request, session: AsyncSession = Depends(get_session)):  # type: ignore[arg-type]
    allowed = {c.strip() for c in settings.google_allowed_client_ids.split(",") if c.strip()}
    if not allowed:
        return problem(request, 501, "Not Implemented", "google sign-in is not configured")
    try:
        claims = google_id_token.verify_oauth2_token(body.id_token, google_requests.Request())
    except Exception:
        return problem(request, 401, "Unauthorized", "invalid google id token")
    if claims.get("aud") not in allowed:
        return problem(request, 401, "Unauthorized", "google token audience not allowed")
    if not claims.get("email_verified"):
        return problem(request, 401, "Unauthorized", "google email not verified")
    email, sub = claims.get("email", ""), claims.get("sub", "")
    if not email or not sub:
        return problem(request, 401, "Unauthorized", "google token missing email/sub")
    user = await auth_service.get_or_create_google_user(session, sub, email)
    access, refresh = await auth_service.issue_pair(session, user.id)
    return {"user": {"id": user.id, "email": user.email}, "access_token": access, "refresh_token": refresh}
