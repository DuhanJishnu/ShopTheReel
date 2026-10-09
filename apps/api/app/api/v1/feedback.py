"""Feedback router: like/dislike/wrong_item/bought per match."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import problem
from app.db import models
from app.db.session import get_session
from app.services import personalisation as perso
from app.workers import queue

router = APIRouter(tags=["feedback"])


class FeedbackIn(BaseModel):
    signal: str


@router.post("/v1/matches/{match_id}/feedback")
async def give_feedback(
    match_id: str, body: FeedbackIn, request: Request,
    user: models.User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # type: ignore[arg-type]
):
    try:
        feedback = await perso.record_feedback(session, user, match_id, body.signal)
    except ValueError:
        return problem(request, 422, "Unprocessable", "signal must be like|dislike|wrong_item|bought")
    except LookupError:
        return problem(request, 404, "Not Found", "match not found")
    await queue.enqueue_taste(feedback.id)
    return {"feedback_id": feedback.id, "signal": feedback.signal}
