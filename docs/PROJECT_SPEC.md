# ShopTheReel — Build Spec for the AI Coding Agent

> Drop this file in the repo root (rename to `AGENTS.md` or `CLAUDE.md` if your agent reads that name).
> It is the single source of truth. Read it fully before writing code.

---

## 0. How you (the agent) must work

1. Work **one phase at a time** (Section 14). Do not start a phase until the previous phase's acceptance criteria pass.
2. Before each phase, print a short plan (files to create, order). After each phase, run tests and report results against the acceptance criteria.
3. **Never invent API signatures.** For `google-genai`, `expo-share-intent`, `pgvector`, `open_clip`/`transformers`, check the installed package's docs or source before use. Model names are in env vars because they change.
4. Small commits, conventional commit messages (`feat:`, `fix:`, `chore:`).
5. Every backend module gets tests (pytest). Every pipeline stage must be runnable alone from a CLI (`python -m app.pipeline.<stage> --help`).
6. If something is ambiguous or blocked, stop and ask the human. Do not silently pick a different stack.
7. Keep secrets out of git. Provide `.env.example` only.
8. Prefer boring, readable code over clever code. Type hints everywhere. `ruff` + `mypy` must pass.

---

## 1. Product summary

**ShopTheReel**: a user shares an Instagram reel (or a screen recording/screenshots of one) to the app. The backend detects every garment/accessory in the reel, matches each to purchasable products, and composes a **full outfit** in three tiers (**Exact / Similar / Budget**), personalised by the user's gender, sizes, budget and taste. A **B2B API** exposes the same pipeline so a retailer (e.g. Myntra, Flipkart) can plug in its own catalog.

Two surfaces:
- **B2C**: Expo mobile app.
- **B2B**: API-key-authenticated `/b2b/v1/*` endpoints + `CatalogProvider` adapter interface.

---

## 2. Key decisions (already made — do not revisit)

| Topic | Decision |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + Alembic |
| Mobile | Expo (TypeScript), expo-router, **development build** (not Expo Go — share intent needs native code) |
| DB | PostgreSQL 16 + `pgvector` (HNSW indexes) |
| Cache/queue broker | Redis 7 |
| Job queue | **ARQ** (async, Redis-based) — simpler than Celery for an async FastAPI codebase |
| Object storage | S3-compatible; **MinIO** locally, any S3 in prod |
| AI | Google Gemini via `google-genai` SDK: vision + structured output; Gemini text embeddings |
| Visual embeddings | FashionCLIP (`patrickjohncyh/fashion-clip`) via `transformers`, 512-d, run in the worker (CPU is fine for demo) |
| Catalog for demo | **Public fashion dataset + mock partner retailer adapter** (Section 8) |
| Instagram ingestion | **Never scrape or download from Instagram.** Ingest = shared link (metadata only), screen-recording/video file, or screenshots (Section 6) |
| Deploy | Docker Compose locally; Render/Fly/any VPS for demo |
| Monorepo | One repo, `apps/api`, `apps/mobile`, `packages/` for shared docs/schemas |

---

## 3. Requirements

### 3.1 Functional

**FR-1 Auth & profile**
- Email+password register/login, JWT access (15 min) + refresh (30 days, rotating).
- Profile: `gender` (`women|men|unisex`), `sizes` (`top`, `bottom`, `shoe`, each with a system like `IN`/`UK`/`US`), `height_cm`, `budget_min/max` (INR), `style_tags[]`, `disliked_colours[]`, `preferred_brands[]`.
- `DELETE /v1/me` removes all user data.

**FR-2 Ingest**
- Mobile app receives shares via OS share sheet: text (URL), video, image(s).
- Direct-to-storage upload through presigned URLs.
- Idempotent reel creation (`Idempotency-Key` header).

**FR-3 Extraction**
- Detect garments and accessories (tops, bottoms, outerwear, dresses, footwear, bags, watches, eyewear, jewellery, headwear).
- Per item: category, subcategory, colours, pattern, fit, material guess, gender hint, bounding box, source frame timestamp, confidence, crop image.
- Merge duplicates of the same item across frames.

**FR-4 Matching**
- Retrieve candidate products by hybrid search: metadata filters + text-embedding + image-embedding fusion.
- Three tiers per item: `exact` (best visual+attribute match), `similar` (same style, different brand), `budget` (cheapest acceptable match, ≤ 60% of the exact price when possible).
- Filter by gender, size-in-stock, budget range, disliked colours.

**FR-5 Outfit**
- Compose a full outfit per tier with total price and per-item buy link.
- "Complete the look": if the reel shows an incomplete outfit (e.g. top only), suggest missing slots (bottom, footwear) matching the detected style.

**FR-6 Personalisation loop**
- Feedback per match: `like`, `dislike`, `wrong_item`, `bought`.
- Maintain a per-user **taste vector** (768-d, same space as text embeddings) updated by exponential moving average on liked/bought items, pushed away from disliked ones.
- Rerank uses taste vector similarity.

**FR-7 Social/Utility**
- Save looks, boards, share a look via link, price-drop alerts (poll job + push notification).

**FR-8 B2B**
- API keys per org, `POST /b2b/v1/analyze`, usage metering, `CatalogProvider` adapter interface, per-key rate limits.

### 3.2 Non-functional

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | End-to-end processing, 30 s reel | p95 < 25 s; cache hit < 3 s |
| NFR-2 | Cost per processed reel (Gemini) | tracked per reel, target < ₹2; log tokens in `reel_costs` |
| NFR-3 | Detection quality | F1 ≥ 0.75 on eval set (Section 12) |
| NFR-4 | Retrieval quality | Recall@10 ≥ 0.6 on eval set |
| NFR-5 | Availability | API stateless; workers horizontally scalable; graceful degradation if Gemini fails (return partial result + retry) |
| NFR-6 | Security | Argon2 password hashing, JWT, signed URLs (5 min), per-IP and per-key rate limits, input size/type validation, CORS allow-list |
| NFR-7 | Privacy | Delete-my-data; raw videos auto-deleted after 7 days; store only crops + metadata long term |
| NFR-8 | Observability | Structured JSON logs with `request_id`/`reel_id`, OpenTelemetry traces, Prometheus metrics, Sentry |
| NFR-9 | Reliability | Idempotent jobs, retries with exponential backoff (max 3), dead-letter table, per-stage status |
| NFR-10 | Testability | ≥ 80% coverage on pipeline + services; Gemini mocked via a `VisionClient` interface |

---

## 4. Architecture

```
Expo app ──share intent / upload──► FastAPI ──► Postgres+pgvector
   ▲  SSE progress                      │         Redis (queue, cache, rate-limit)
   │                                    ▼         MinIO/S3 (videos, crops)
   │                              ARQ job queue
   │                                    ▼
   │      ┌──────────────── Pipeline worker ────────────────┐
   │      │ ingest → preprocess → extract → crop/merge →    │
   │      │ embed → retrieve → rerank → compose outfit      │
   │      └─────────────────────────────────────────────────┘
   │                                    ▲
   └── results ◄── personalisation ◄── catalog (provider adapters + embeddings)
```

Design rules:
- API never runs the pipeline inline. It enqueues and returns `202` with the reel id.
- Each pipeline stage reads/writes DB + storage and is **idempotent** (re-running yields the same state). Persist `reel.status` and `reel_stages` rows.
- All external calls (Gemini, storage) sit behind interfaces: `VisionClient`, `TextEmbedder`, `ImageEmbedder`, `ObjectStore`, `CatalogProvider`. Provide real + fake implementations.

---

## 5. Repository layout

```
shopthereel/
├─ PROJECT_SPEC.md
├─ docker-compose.yml
├─ .env.example
├─ Makefile                      # make up, make test, make lint, make seed, make eval
├─ .github/workflows/ci.yml
├─ apps/
│  ├─ api/
│  │  ├─ pyproject.toml          # uv or poetry
│  │  ├─ alembic/
│  │  ├─ app/
│  │  │  ├─ main.py
│  │  │  ├─ core/                # config, security, logging, errors, deps
│  │  │  ├─ db/                  # base, session, models/
│  │  │  ├─ schemas/             # pydantic request/response models
│  │  │  ├─ api/v1/              # routers: auth, profile, uploads, reels, looks, feedback, alerts, b2b, catalog
│  │  │  ├─ services/            # business logic (profile, reels, personalisation, outfit)
│  │  │  ├─ clients/             # vision.py, embeddings.py, storage.py (interfaces + impls + fakes)
│  │  │  ├─ pipeline/            # ingest.py, preprocess.py, extract.py, crop_merge.py, embed.py,
│  │  │  │                       # retrieve.py, rerank.py, compose.py, orchestrator.py
│  │  │  ├─ catalog/             # provider.py (interface), providers/dataset.py, providers/mock_partner.py, ingest.py
│  │  │  ├─ workers/             # arq settings, tasks
│  │  │  └─ eval/                # harness, metrics, labelled set loader
│  │  └─ tests/
│  └─ mobile/
│     ├─ app/                    # expo-router screens
│     ├─ src/{api,components,hooks,store,theme}/
│     └─ app.config.ts
├─ data/
│  ├─ raw/                       # downloaded dataset (gitignored)
│  └─ eval/                      # labelled eval reels metadata (JSON) — small, committed
└─ docs/                         # architecture.md, api.md, eval-report.md
```

---

## 6. Ingestion design (important — read carefully)

Instagram does **not** hand the video to other apps. Support three paths, all ending at the same `POST /v1/reels`:

1. **Video file** (primary): user screen-records the reel or shares a saved video; the app receives a file URI via the share intent, uploads via presigned URL, then calls `POST /v1/reels {storage_key}`.
2. **Screenshots** (1–6 images): same flow with `kind="images"`.
3. **Link** (`kind="link"`): store the URL as `source_url` and create the reel in `needs_media` status. The app then prompts: "Add a screen recording or screenshots to analyse this reel." Do **not** fetch or download media from Instagram. (Optionally display the oEmbed thumbnail if the user configured a token — skip in MVP.)

Mobile implementation notes:
- Use `expo-share-intent`; it requires a dev build (`npx expo prebuild` / EAS dev client). Configure Android intent filters for `text/plain`, `video/*`, `image/*`, and the iOS Share Extension per the library's docs.
- Handle the case where the app is cold-started by a share.
- Compress video client-side if > 50 MB (expo-video-thumbnails / ffmpeg-kit optional; if not available, enforce a 100 MB cap and show a friendly error).

---

## 7. Pipeline specification

### 7.1 Stages and statuses

`reel.status`: `needs_media → queued → preprocessing → extracting → embedding → matching → composing → done | failed | partial`

Each stage writes a `reel_stages` row (`stage`, `status`, `started_at`, `ended_at`, `error`, `metrics jsonb`) and publishes an event to Redis channel `reel:{id}` for SSE.

### 7.2 Stage details

**ingest**: compute SHA-256 of bytes and a perceptual video hash (sample 8 frames → pHash → concat). If another `done` reel has the same sha256 **or** perceptual-hash Hamming distance ≤ 6 → copy its results to this reel (`cache_hit=true`) and finish. Validate: duration ≤ 90 s, size ≤ 100 MB, MIME in allow-list.

**preprocess** (ffmpeg via `ffmpeg-python` or subprocess; ffmpeg is installed in the worker Docker image):
- Normalise to 720p max, strip audio.
- Scene detection (PySceneDetect `ContentDetector`).
- Sample candidate frames: 1 per scene + 1 per 2 s fallback, up to 24 candidates.
- Score candidates (sharpness via Laplacian variance, plus person-area via a Gemini-free heuristic or the first Gemini pass) and keep the best **8** frames after perceptual-hash dedupe. Store in `frames/{reel_id}/{idx}.jpg`.

**extract** (Gemini vision):
- Send the 8 frames (as inline images) with the system prompt and JSON schema from Section 7.3 to `GEMINI_VISION_MODEL`.
- Use structured output (`response_mime_type="application/json"` + `response_schema`). Validate with Pydantic; on invalid JSON retry once with the validation error appended.
- Temperature 0.1. Log token usage to `reel_costs`.
- Bounding boxes are normalised `[ymin, xmin, ymax, xmax]` in 0–1000 coordinates (Gemini convention) — convert to pixels. Verify against the SDK docs.

**crop_merge**:
- Crop each bbox with 8% padding. Skip crops smaller than 64 px on the short side.
- Compute image embedding (FashionCLIP) per crop. Cluster items of the same `category` across frames (cosine sim > 0.88 → same item), keep the highest-confidence/largest crop as the representative; merge attribute lists by majority vote.
- Save `crops/{reel_id}/{item_id}.jpg`.

**embed**:
- Build `attribute_text` for each item: `"{colour} {pattern} {fit} {subcategory} for {gender_hint}, {material}"`.
- Text embedding: Gemini embedding model, `output_dimensionality=768`, L2-normalise.
- Image embedding: FashionCLIP on the crop (512-d, normalised).
- Store both on `detected_items`.

**retrieve**:
- Hard filters (SQL): `gender IN (user_gender, 'unisex')`, `category` compatible, `in_stock`, requested size in `sizes_available`, `disliked_colours` excluded, price within `[budget_min*0.5, budget_max*1.5]` (soft-widened; flag out-of-budget).
- Two ANN queries (pgvector `<=>`): text-vector and image-vector, top 50 each, union.
- Fuse: `score = 0.5*img_sim + 0.35*text_sim + 0.15*attr_match` where `attr_match` = fraction of detected colour/pattern/fit tags matched.

**rerank**:
- Add personalisation: `+ 0.15 * cosine(taste_vec, product_text_vec)` `+ 0.05 * brand_pref` `− 0.1 * price_over_budget_ratio`.
- Optional LLM rerank (feature flag `LLM_RERANK=true`): send top 8 candidate thumbnails/titles + the crop to Gemini, get an ordered list with a one-line reason ("same cut, slightly darker wash"). Store `reason`.

**compose**:
- For each detected item, choose: `exact` = top rerank score; `similar` = best candidate with a different brand and sim ≥ 0.6; `budget` = cheapest candidate with score ≥ 0.75 × exact score.
- Missing-slot completion: if the outfit lacks `bottom` or `footwear` (dress counts as top+bottom), query for those slots using the outfit's dominant colour palette + style tags and mark them `suggested=true`.
- Compute tier totals. Persist `matches` rows.

### 7.3 Gemini extraction schema and prompt

System prompt (store in `app/pipeline/prompts/extract_v1.md`, version it):

```
You are a fashion analyst. You receive up to 8 frames from a short video of a person.
Identify every distinct garment and accessory worn by the MAIN person(s). Ignore background people unless
they are clearly the focus. For each item, give precise, shopper-oriented attributes.
Rules:
- One entry per distinct item, even if seen in several frames (reference the best frame).
- Use only the allowed enums. If unsure, use "unknown" and lower the confidence.
- Colours are simple names (e.g. "olive green", "off-white").
- Do not guess brands unless a logo is clearly visible.
- bbox is [ymin, xmin, ymax, xmax] in 0-1000 coordinates of the referenced frame.
Return JSON only.
```

Response schema (Pydantic → JSON schema):

```python
class DetectedItem(BaseModel):
    category: Literal["top","bottom","dress","outerwear","footwear","bag","watch","eyewear","jewellery","headwear","belt","scarf","other"]
    subcategory: str                     # e.g. "oversized t-shirt", "straight-fit jeans", "chunky sneakers"
    colours: list[str]                   # primary first
    pattern: Literal["solid","striped","checked","floral","graphic","printed","textured","other","unknown"]
    fit: Literal["slim","regular","relaxed","oversized","cropped","unknown"]
    material_guess: str | None
    gender_hint: Literal["women","men","unisex","unknown"]
    style_tags: list[str]                # e.g. ["streetwear","casual"]
    frame_index: int                     # which input frame is best
    bbox: list[int]                      # 4 ints, 0-1000
    brand_visible: str | None
    confidence: float                    # 0-1

class ExtractionResult(BaseModel):
    items: list[DetectedItem]
    overall_style: list[str]
    occasion_guess: Literal["casual","college","office","party","wedding","sport","travel","unknown"]
    dominant_palette: list[str]
```

---

## 8. Catalog plan (demo)

**Source**: the public **Fashion Product Images (Small/Full) dataset** on Kaggle (product images + `styles.csv` with `gender`, `masterCategory`, `subCategory`, `articleType`, `baseColour`, `season`, `usage`, `productDisplayName`). It originates from an Indian fashion retailer's catalog, so categories and colours suit the Indian market. Before using it, the human must download it manually (Kaggle login) into `data/raw/` and confirm they accept its licence. Use it for demo/educational purposes only and say so in the README.

**Gaps the seed script must fill (deterministically, seeded RNG)**:
- `price`: by `articleType` price bands (e.g. t-shirt ₹399–1299, jeans ₹799–2499, sneakers ₹1299–5999) with a brand multiplier.
- `brand`: parse from `productDisplayName` first token(s), else "Generic".
- `sizes_available`: per category size set (tops: XS–XXL; bottoms: 28–38; shoes: UK 5–11), randomly drop some sizes; `in_stock` ~90%.
- `buy_url`: from the partner's `buy_url_template`. For the mock partner use `https://partner.example/p/{sku}` and show a visible "Demo partner" badge in the UI — **do not present fake links as real purchase links**.

**Scale for demo**: seed **~10,000 products** (balanced across categories). Embedding all of them with FashionCLIP on CPU is slow, so batch (32) and checkpoint progress so the script is resumable. Gemini text embeddings in batches with backoff.

**Provider abstraction** (this is the B2B story):

```python
class CatalogProvider(Protocol):
    name: str
    async def search_candidates(self, query: CandidateQuery) -> list[ProductCandidate]: ...
    async def get_product(self, sku: str) -> Product | None: ...
    async def check_availability(self, sku: str, size: str) -> Availability: ...
```

Implementations:
1. `DatasetProvider`: queries the local `products` table (pgvector). Default.
2. `MockPartnerProvider`: simulates a remote retailer REST API with latency, pagination, occasional 5xx and rate limits, using the same data. Proves the adapter pattern, retries and circuit breaker.
3. Document in `docs/` how a real Myntra/Flipkart adapter would implement the interface (their search API or feed).

Retrieval fans out to enabled providers in parallel (`asyncio.gather` with per-provider timeout 2 s) and merges results.

---

## 9. Data model (PostgreSQL)

Use UUID PKs, `created_at/updated_at` on everything. Key tables:

```sql
users(id, email unique, password_hash, created_at)
profiles(user_id pk fk, gender, sizes jsonb, height_cm, budget_min, budget_max,
         style_tags text[], disliked_colours text[], preferred_brands text[],
         taste_vec vector(768), taste_updated_at)
refresh_tokens(id, user_id, token_hash, expires_at, revoked_at)

reels(id, user_id, kind, source_url, storage_key, sha256, phash, status, cache_hit bool,
      duration_s, overall_style text[], occasion, error, created_at)
reel_stages(id, reel_id, stage, status, started_at, ended_at, error, metrics jsonb)
reel_costs(id, reel_id, model, input_tokens, output_tokens, est_cost_inr)
frames(id, reel_id, idx, storage_key, sharpness)

detected_items(id, reel_id, category, subcategory, colours text[], pattern, fit, material_guess,
               gender_hint, style_tags text[], bbox jsonb, crop_key, confidence,
               attribute_text, text_vec vector(768), image_vec vector(512), suggested bool)

products(id, provider, sku, title, brand, category, subcategory, gender, colours text[], pattern,
         fit, price numeric, currency, sizes_available text[], in_stock bool, image_url, buy_url,
         attribute_text, text_vec vector(768), image_vec vector(512), updated_at,
         unique(provider, sku))
-- HNSW indexes on text_vec and image_vec (vector_cosine_ops); btree on (gender, category, in_stock)

matches(id, item_id, product_id, tier, score, reason, rank)
looks(id, user_id, reel_id, title, is_public, share_slug)
look_items(look_id, match_id)
boards(id, user_id, name), board_looks(board_id, look_id)
feedback(id, user_id, match_id, signal, created_at)
price_alerts(id, user_id, product_id, target_price, last_notified_at)

orgs(id, name), api_keys(id, org_id, key_hash, prefix, rate_limit_per_min, revoked_at)
usage_events(id, org_id, endpoint, reel_id, cost_units, created_at)
dead_letters(id, job, payload jsonb, error, created_at)
```

---

## 10. API specification (`/v1`, JSON, Bearer JWT unless noted)

Conventions: Pydantic v2 schemas, RFC 7807 problem+json errors, cursor pagination (`?cursor=&limit=`), `X-Request-ID`, rate-limit headers, OpenAPI at `/docs`.

### Auth
- `POST /v1/auth/register` `{email,password}` → `201 {user, access_token, refresh_token}`
- `POST /v1/auth/login` → tokens
- `POST /v1/auth/refresh` `{refresh_token}` → rotated tokens
- `POST /v1/auth/logout` → revoke refresh token

### Profile
- `GET /v1/me/profile`, `PUT /v1/me/profile`
- `DELETE /v1/me` → `204` (cascade delete + storage cleanup job)

### Uploads
- `POST /v1/uploads/presign` `{content_type, size_bytes, kind}` → `{upload_url, storage_key, expires_at}`

### Reels
- `POST /v1/reels` header `Idempotency-Key` · body `{kind: "video"|"images"|"link", storage_keys?: [], source_url?: string}` → `202 {id, status}`
- `GET /v1/reels/{id}` → status, per-stage progress, cache_hit, overall_style, occasion
- `GET /v1/reels/{id}/events` → **SSE** stream: `stage`, `progress`, `done`, `error`
- `GET /v1/reels/{id}/items` → detected items with crop URLs
- `GET /v1/reels/{id}/outfit?tier=exact|similar|budget` → `{tier, items:[{item, match:{product, score, reason}, suggested}], total_price, currency}`
- `GET /v1/reels?cursor=` → history
- `POST /v1/reels/{id}/retry`

### Matches & feedback
- `GET /v1/items/{item_id}/alternatives?limit=10`
- `POST /v1/matches/{id}/feedback` `{signal: "like"|"dislike"|"wrong_item"|"bought"}` → updates taste vector asynchronously

### Looks, boards, alerts
- `GET/POST /v1/looks`, `GET /v1/looks/{id}`, `POST /v1/looks/{id}/share` → `{share_url}`, `GET /v1/public/looks/{slug}` (no auth)
- `GET/POST /v1/boards`, `POST /v1/boards/{id}/looks`
- `POST /v1/alerts/price`, `GET /v1/alerts`, `DELETE /v1/alerts/{id}`

### Catalog (admin token)
- `POST /v1/catalog/products:bulk`, `POST /v1/catalog/reindex`

### B2B (header `X-API-Key`)
- `POST /b2b/v1/analyze` `{media_url | storage_key, provider?: "partner-id", options:{tiers:[...], gender?, budget?}}` → `202 {job_id}`
- `GET /b2b/v1/jobs/{id}` → result when done (items + matches, using the retailer's catalog provider)
- `GET /b2b/v1/usage?from=&to=`
- Webhook option: `callback_url` receives the result with an HMAC signature header.

### Health
- `GET /healthz`, `GET /readyz` (DB, Redis, storage), `GET /metrics` (Prometheus)

---

## 11. Mobile app spec (Expo)

Screens (expo-router):
1. **Onboarding**: gender → sizes → budget slider → style tag picker (visual chips).
2. **Home**: recent looks, "Share a reel to get started" empty state with a short how-to.
3. **Share receiver**: opens on share intent; shows preview, kind selector, "Analyse" button; link-only shares show the "add screen recording/screenshots" prompt.
4. **Processing**: live stage progress via SSE (fallback to polling every 2 s).
5. **Outfit result**: reel crop strip on top, tier segmented control (Exact / Similar / Budget), item cards (crop vs matched product image, price, size chip, "why this match" reason, Buy button → opens `buy_url` in in-app browser), total price bar, ♡ / ✕ / "wrong item" actions, "Complete the look" section.
6. **Saved**: looks and boards.
7. **Profile/Settings**: edit sizes/budget, Style DNA visual, delete account.

Tech: TanStack Query for server state, Zustand for UI state, `expo-secure-store` for tokens, an API client generated from the OpenAPI schema (`openapi-typescript`), a dark/light theme, skeleton loaders, error boundaries, haptics on feedback.

---

## 12. Evaluation harness (a differentiator — build it)

- `data/eval/` holds ~60–100 entries: `{video_or_frames_path, expected_items:[{category, colours, pattern}]}`. The human supplies the media (own recordings/royalty-free clips); you provide the loader, the JSON format and a template. Do not download third-party reels.
- `make eval` runs the pipeline in "eval mode" and reports:
  - **Detection**: precision/recall/F1 (match on category + colour overlap).
  - **Retrieval**: Recall@1/5/10 against hand-labelled acceptable product SKUs for a subset.
  - **Latency**: p50/p95 per stage and total.
  - **Cost**: mean ₹ per reel.
- Output `docs/eval-report.md` (auto-generated table). Run on CI against a tiny smoke set with the fake Gemini client; run the full set manually.

---

## 13. Quality, ops and security checklist

- `docker compose up` brings up api, worker, postgres, redis, minio, plus optional prometheus/grafana profile.
- CI (GitHub Actions): ruff, mypy, pytest with Postgres/Redis service containers, Expo typecheck + lint, Docker build.
- Rate limiting via Redis token bucket (per IP for B2C, per key for B2B).
- Input validation: MIME sniffing (not just the extension), size caps, ffmpeg run with timeout and resource limits.
- Retries: stage-level (3×, exponential backoff + jitter); Gemini 429/5xx handled with a circuit breaker; failures after retries → `dead_letters`.
- Secrets via env only. Pre-commit hooks for secret scanning.
- Load test with k6 (upload→job enqueue path and read endpoints) and record the results in `docs/`.

---

## 14. Phases, tasks and acceptance criteria

### Phase 1 — Foundations (weeks 1–2)
Tasks
- [ ] Monorepo scaffold, Docker Compose (api, worker, postgres+pgvector, redis, minio), Makefile, CI.
- [ ] Config (pydantic-settings), logging, error handling (problem+json), request-id middleware.
- [ ] Alembic migrations: users, profiles, refresh_tokens, reels, reel_stages.
- [ ] Auth endpoints with Argon2 + JWT rotation; profile CRUD.
- [ ] `ObjectStore` interface + MinIO impl; `POST /uploads/presign`.
- [ ] Expo app: onboarding, auth, profile, API client, secure token storage.
- [ ] `expo-share-intent` configured; share receiver screen uploads a video/image to storage.

Acceptance
- `make up && make test` green. A user can register, set a profile, share a video from the phone's gallery to the app and see it in storage. `GET /readyz` is green.

### Phase 2 — Extraction MVP (weeks 3–4)
Tasks
- [ ] `POST /reels`, idempotency, ARQ worker, stage tracking, SSE events.
- [ ] ingest (hashing + cache), preprocess (ffmpeg, scene detection, frame selection).
- [ ] `VisionClient` interface + Gemini impl + fake impl; extraction prompt v1; schema validation + retry; cost logging.
- [ ] crop_merge with FashionCLIP embeddings; crops saved.
- [ ] Mobile: processing screen + items view with crops.

Acceptance
- A 30 s video produces a list of detected items with crops and attributes in < 25 s p95 on the dev machine; re-uploading the same video returns instantly (`cache_hit=true`); unit tests cover each stage with the fake client.

### Phase 3 — Catalog and retrieval (weeks 5–6)
Tasks
- [ ] Products table + HNSW indexes; seed script (dataset → ~10k products, synthetic price/brand/sizes, resumable).
- [ ] `TextEmbedder` (Gemini) and `ImageEmbedder` (FashionCLIP) interfaces/impls.
- [ ] `CatalogProvider` interface, `DatasetProvider`, `MockPartnerProvider`.
- [ ] retrieve + fuse; matches persisted; `GET /reels/{id}/outfit` (single tier first).
- [ ] Mobile outfit screen with item cards and buy buttons (demo-partner badge).

Acceptance
- End-to-end: shared video → outfit with product matches shown in the app. Retrieval query p95 < 300 ms for the top-50 ANN on the 10k catalog.

### Phase 4 — Personalisation (weeks 7–8)
Tasks
- [ ] Size/gender/budget/disliked-colour filters; soft budget widening with an "over budget" flag.
- [ ] Rerank with taste vector, brand preference; optional LLM rerank behind a flag; reasons stored.
- [ ] Three tiers; outfit totals; "complete the look".
- [ ] Feedback endpoint; taste-vector EMA update job; Style DNA screen.
- [ ] Looks, boards, share links.

Acceptance
- Changing the profile size/budget changes results; liking items measurably shifts later rankings (test with a synthetic user: after 5 likes of one style, that style's items rank higher); three tiers always satisfy price ordering constraints when candidates exist.

### Phase 5 — Scale and quality (weeks 9–10)
Tasks
- [ ] Rate limiting, circuit breaker, dead-letter handling, retries, per-stage metrics.
- [ ] OpenTelemetry + Prometheus + Grafana dashboard, Sentry.
- [ ] Evaluation harness + `docs/eval-report.md`; k6 load test results.
- [ ] Raw-video retention job (7 days), delete-my-data flow.
- [ ] Price-drop alert poller + push notifications.

Acceptance
- Eval report generated with F1, Recall@k, p95 latency, cost/reel. Killing the Gemini client mid-run yields a `partial` or retried result, never a stuck job. Load test shows API stays responsive while 20 jobs are queued.

### Phase 6 — B2B layer (weeks 11–12)
Tasks
- [ ] Orgs, API keys (hashed, prefix shown once), per-key rate limits, usage metering.
- [ ] `/b2b/v1/analyze`, jobs, usage, HMAC-signed webhooks.
- [ ] Provider selection per org; provider adapter docs for a "Myntra-like" and "Flipkart-like" integration.
- [ ] Minimal web demo page (static HTML or small Next.js) showing an embeddable "Shop the Reel" widget calling the B2B API.
- [ ] `docs/api.md` + Postman/Bruno collection.

Acceptance
- A curl with an API key analyses a video against the mock partner's catalog and receives a signed webhook. Usage endpoint matches the number of calls made.

### Phase 7 — Polish (week 13+)
- [ ] Wardrobe-aware mode (user lists owned items → suppress duplicates, suggest missing pieces).
- [ ] Occasion re-ranking; size-confidence score from feedback (`bought`, `wrong_item`, returns).
- [ ] README with architecture diagram, benchmarks, demo GIFs; 2-minute demo video script; architecture write-up in `docs/architecture.md`.
- [ ] EAS build for Android APK.

---

## 15. Environment variables (`.env.example`)

```
APP_ENV=dev
DATABASE_URL=postgresql+asyncpg://shop:shop@postgres:5432/shopthereel
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT=http://minio:9000
S3_BUCKET=shopthereel
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
JWT_SECRET=change-me
GEMINI_API_KEY=
GEMINI_VISION_MODEL=gemini-2.5-flash        # verify current model names before use
GEMINI_EMBED_MODEL=gemini-embedding-001     # verify; request output_dimensionality=768
LLM_RERANK=false
MAX_VIDEO_MB=100
MAX_VIDEO_SECONDS=90
RAW_VIDEO_RETENTION_DAYS=7
SENTRY_DSN=
```

---

## 16. Out of scope (do not build)

- Downloading/scraping Instagram media or any retailer site.
- Real payments/checkout (buy links open the retailer).
- Real Myntra/Flipkart credentials or integrations (adapter interface + mock only).

---

## 17. Questions the agent should ask the human at the right time

- Phase 1 start: which OS/devices will be used for testing share intent (Android first is recommended; iOS needs an Apple developer setup for the Share Extension on device)?
- Phase 3 start: confirm the dataset is downloaded into `data/raw/` and the licence is accepted.
- Phase 5 start: provide the eval media (60–100 short clips the human owns/has rights to).
