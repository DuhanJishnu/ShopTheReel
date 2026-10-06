# ShopTheReel — Phase 1 (Foundations)

## What is this?
Share an Instagram reel (video file / screenshots / link) → backend detects garments → matches to products → 3-tier outfit. Phase 1 covers foundations only: auth, profile, presigned uploads, health, Expo shell + share receiver.

## Architecture
```
Expo app --share intent / upload--> FastAPI --> Postgres+pgvector
   ^  (Phase 2: SSE progress)        |          Redis (queue/cache)
   |                                  v          MinIO/S3 (videos, crops)
   |                             ARQ worker (Phase 1: placeholder idle)
```

## One-command local start
1. `cp .env.example .env` (set `JWT_SECRET`)
2. `make up` — brings up api, worker, postgres, redis, minio
3. API: `http://localhost:8000/docs`, `GET /healthz`, `GET /readyz`

## Mobile dev build (Android first)
- Requires a **development build** (share intent needs native code; won't work in Expo Go).
- `cd apps/mobile && npm install`
- `npx expo prebuild` (generates android/, gitignored) then `npm run android` or EAS dev client.
- Set `EXPO_PUBLIC_API_URL=http://10.0.2.2:8000` (emulator) or your LAN IP for device.
- Share a video/image from gallery → ShopTheReel → Share receiver → Analyse uploads via presigned URL.

## Tests / lint
- `make test` (pytest; SQLite by default, Postgres via `DATABASE_URL_TEST` in CI)
- `make lint` (ruff + mypy + ESLint + tsc)
- `make migrate` (alembic upgrade head)

## Known Phase-1 gaps
- `profiles.taste_vec` is JSON nullable; Phase 3 alters to `vector(768)` + HNSW.
- No `/v1/reels` pipeline yet (Phase 2). Share upload ends at storage.
- `readyz` reports per-check booleans; 503 when deps unavailable.
