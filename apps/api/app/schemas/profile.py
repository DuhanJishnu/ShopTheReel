"""Pydantic v2 schemas for profile."""

from typing import Literal

from pydantic import BaseModel, Field

Gender = Literal["women", "men", "unisex"]


class ProfileIn(BaseModel):
    gender: Gender | None = None
    sizes: dict | None = None
    height_cm: float | None = Field(default=None, ge=100, le=250)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    style_tags: list[str] = Field(default_factory=list)
    disliked_colours: list[str] = Field(default_factory=list)
    preferred_brands: list[str] = Field(default_factory=list)


class ProfileOut(ProfileIn):
    user_id: str
