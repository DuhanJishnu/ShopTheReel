"""ARQ worker entrypoint (Phase 1: placeholder, no jobs yet).

Phase 2 will register pipeline tasks here. Kept so `docker compose up`
brings up a worker service that stays alive and healthy.
"""

import asyncio


async def startup(ctx: dict) -> None:
    print("worker startup (phase-1 placeholder)")


async def shutdown(ctx: dict) -> None:
    print("worker shutdown")


class WorkerSettings:
    functions: list = []
    on_startup = startup
    on_shutdown = shutdown


if __name__ == "__main__":
    # Keep the container alive without ARQ jobs in Phase 1.
    async def _idle() -> None:
        await startup({})
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await shutdown({})

    asyncio.run(_idle())
