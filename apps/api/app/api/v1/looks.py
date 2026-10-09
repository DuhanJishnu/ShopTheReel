"""Looks, boards, and share links."""

import secrets

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import problem
from app.db import models
from app.db.session import get_session

router = APIRouter(tags=["looks"])


class LookIn(BaseModel):
    title: str = "Untitled look"
    reel_id: str | None = None
    match_ids: list[str] = []


class BoardIn(BaseModel):
    name: str


class BoardLookIn(BaseModel):
    look_id: str


async def _owned_look(session: AsyncSession, user_id: str, look_id: str) -> models.Look | None:
    look = await session.get(models.Look, look_id)
    return look if look is not None and look.user_id == user_id else None


def _look_out(look: models.Look) -> dict:
    base = f"/v1/public/looks/{look.share_slug}" if look.share_slug else None
    return {"id": look.id, "title": look.title, "is_public": look.is_public,
            "share_slug": look.share_slug, "share_url": base}


@router.post("/v1/looks", status_code=201)
async def create_look(
    body: LookIn, user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
):
    look = models.Look(user_id=user.id, reel_id=body.reel_id, title=body.title)
    session.add(look)
    await session.flush()
    for mid in body.match_ids:
        if await session.get(models.Match, mid) is not None:
            session.add(models.LookItem(look_id=look.id, match_id=mid))
    await session.commit()
    return _look_out(look)


@router.get("/v1/looks")
async def list_looks(
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> dict:
    res = await session.execute(select(models.Look).where(models.Look.user_id == user.id))
    return {"items": [_look_out(look) for look in res.scalars().all()]}


@router.get("/v1/looks/{look_id}")
async def get_look(
    look_id: str, request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
):
    look = await _owned_look(session, user.id, look_id)
    if look is None:
        return problem(request, 404, "Not Found", "look not found")
    res = await session.execute(select(models.LookItem).where(models.LookItem.look_id == look.id))
    return {**_look_out(look), "match_ids": [li.match_id for li in res.scalars().all()]}


@router.post("/v1/looks/{look_id}/share")
async def share_look(
    look_id: str, request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
):
    look = await _owned_look(session, user.id, look_id)
    if look is None:
        return problem(request, 404, "Not Found", "look not found")
    if not look.share_slug:
        look.share_slug = secrets.token_urlsafe(8)
    look.is_public = True
    await session.commit()
    return {"share_url": f"/v1/public/looks/{look.share_slug}"}


@router.get("/v1/public/looks/{slug}")
async def public_look(slug: str, request: Request, session: AsyncSession = Depends(get_session)):  # type: ignore[arg-type]
    res = await session.execute(
        select(models.Look).where(models.Look.share_slug == slug, models.Look.is_public.is_(True)))
    look = res.scalars().first()
    if look is None:
        return problem(request, 404, "Not Found", "look not found")
    items = await session.execute(select(models.LookItem).where(models.LookItem.look_id == look.id))
    return {**_look_out(look), "match_ids": [li.match_id for li in items.scalars().all()]}


@router.post("/v1/boards", status_code=201)
async def create_board(
    body: BoardIn, user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> dict:
    board = models.Board(user_id=user.id, name=body.name)
    session.add(board)
    await session.commit()
    await session.refresh(board)
    return {"id": board.id, "name": board.name}


@router.get("/v1/boards")
async def list_boards(
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
) -> dict:
    res = await session.execute(select(models.Board).where(models.Board.user_id == user.id))
    out = []
    for board in res.scalars().all():
        links = await session.execute(select(models.BoardLook).where(models.BoardLook.board_id == board.id))
        out.append({"id": board.id, "name": board.name,
                    "look_ids": [bl.look_id for bl in links.scalars().all()]})
    return {"items": out}


@router.post("/v1/boards/{board_id}/looks")
async def add_board_look(
    board_id: str, body: BoardLookIn, request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
):
    board = await session.get(models.Board, board_id)
    if board is None or board.user_id != user.id:
        return problem(request, 404, "Not Found", "board not found")
    if await _owned_look(session, user.id, body.look_id) is None:
        return problem(request, 404, "Not Found", "look not found")
    session.add(models.BoardLook(board_id=board.id, look_id=body.look_id))
    await session.commit()
    res = await session.execute(select(models.BoardLook).where(models.BoardLook.board_id == board.id))
    return {"id": board.id, "look_ids": [bl.look_id for bl in res.scalars().all()]}
