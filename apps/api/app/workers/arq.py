"""ARQ worker entrypoint. run_worker signature verified against installed arq."""

from arq import run_worker

from app.core.logging import configure_logging, get_logger
from app.workers.queue import redis_settings
from app.workers.tasks import process_reel, update_taste

configure_logging()
log = get_logger()


async def startup(ctx: dict) -> None:
    log.info("worker startup", functions=["process_reel", "update_taste"])


async def shutdown(ctx: dict) -> None:
    log.info("worker shutdown")


class WorkerSettings:
    functions = [process_reel, update_taste]
    redis_settings = redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_tries = 3
    job_timeout = 600


if __name__ == "__main__":
    run_worker(WorkerSettings)  # type: ignore[arg-type]
