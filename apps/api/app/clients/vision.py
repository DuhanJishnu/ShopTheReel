"""VisionClient interface + Gemini implementation + fake.

Gemini usage below was checked against the installed google-genai SDK:
Client(api_key=...), client.aio.models.generate_content(model, contents, config),
GenerateContentConfig(system_instruction, temperature, response_mime_type,
response_schema). Frame bytes are passed as PIL Images (a documented contents
type) to avoid depending on Part helpers.
"""

import io
from typing import Literal, Protocol

import PIL.Image
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger()

Category = Literal[
    "top", "bottom", "dress", "outerwear", "footwear", "bag",
    "watch", "eyewear", "jewellery", "headwear", "belt", "scarf", "other",
]
Pattern = Literal["solid", "striped", "checked", "floral", "graphic", "printed", "textured", "other", "unknown"]
Fit = Literal["slim", "regular", "relaxed", "oversized", "cropped", "unknown"]
GenderHint = Literal["women", "men", "unisex", "unknown"]


class DetectedItemIn(BaseModel):
    category: Category
    subcategory: str = ""
    colours: list[str] = Field(default_factory=list)
    pattern: Pattern = "unknown"
    fit: Fit = "unknown"
    material_guess: str | None = None
    gender_hint: GenderHint = "unknown"
    style_tags: list[str] = Field(default_factory=list)
    frame_index: int = 0
    bbox: list[int] = Field(default_factory=lambda: [0, 0, 1000, 1000])
    brand_visible: str | None = None
    confidence: float = 0.0


class ExtractionResult(BaseModel):
    items: list[DetectedItemIn] = Field(default_factory=list)
    overall_style: list[str] = Field(default_factory=list)
    occasion_guess: Literal["casual", "college", "office", "party", "wedding", "sport", "travel", "unknown"] = "unknown"
    dominant_palette: list[str] = Field(default_factory=list)


class VisionClient(Protocol):
    name: str
    last_usage: dict[str, int]

    async def extract(self, frames: list[bytes]) -> ExtractionResult: ...


def load_prompt() -> str:
    from pathlib import Path

    return (Path(__file__).parent.parent / "pipeline" / "prompts" / "extract_v1.md").read_text()


class GeminiVision:
    """Real Gemini vision extractor. Retries once on schema validation failure."""

    name = "gemini"

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)
        self._model = model or settings.gemini_vision_model
        self.last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    async def extract(self, frames: list[bytes]) -> ExtractionResult:
        images = [PIL.Image.open(io.BytesIO(f)).convert("RGB") for f in frames]
        prompt = load_prompt()
        try:
            return await self._call(prompt, images)
        except ValueError as exc:
            log.warning("extraction validation failed, retrying", error=str(exc))
            return await self._call(f"{prompt}\n\nPrevious output was invalid: {exc}\nReturn valid JSON only.", images)

    async def _call(self, prompt: str, images: list[PIL.Image.Image]) -> ExtractionResult:
        config = types.GenerateContentConfig(
            system_instruction=prompt,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=ExtractionResult.model_json_schema(),
        )
        resp = await self._client.aio.models.generate_content(
            model=self._model, contents=[*images], config=config  # type: ignore[arg-type]
        )
        usage = getattr(resp, "usage_metadata", None)
        self.last_usage = {
            "input_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
            "output_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
        }
        return ExtractionResult.model_validate_json(resp.text or "{}")


class FakeVision:
    """Deterministic fake for tests and key-less local runs. Never calls Gemini."""

    name = "fake"

    def __init__(self) -> None:
        self.last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    async def extract(self, frames: list[bytes]) -> ExtractionResult:
        items = [
            DetectedItemIn(
                category="top", subcategory="t-shirt", colours=["olive green"],
                pattern="solid", fit="oversized", frame_index=0,
                bbox=[200, 300, 600, 700], confidence=0.9, style_tags=["casual"],
            ),
            DetectedItemIn(
                category="bottom", subcategory="jeans", colours=["blue"],
                pattern="solid", fit="regular", frame_index=0,
                bbox=[300, 300, 700, 900], confidence=0.85, style_tags=["casual"],
            ),
        ]
        return ExtractionResult(items=items, overall_style=["casual"], occasion_guess="casual",
                                dominant_palette=["olive green", "blue"])


def get_vision_client() -> VisionClient:
    if settings.gemini_api_key:
        return GeminiVision()
    log.warning("GEMINI_API_KEY unset, using FakeVision")
    return FakeVision()
