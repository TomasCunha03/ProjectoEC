import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from chat_saude.observability.logger import get_logger

from .chat import router as chat_router

logger = get_logger(__name__)


def _run_startup_eval_if_enabled() -> None:
    flag = os.getenv("RUN_STARTUP_EVAL", "").strip().lower()
    if flag not in ("1", "true", "yes"):
        return
    # Local import: keeps normal API imports light and avoids eval during tests that import app.
    from api.eval import run_startup_eval

    ok = run_startup_eval()
    if not ok:
        logger.warning("Startup eval reported failures; API will still start")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_startup_eval_if_enabled()
    yield


app = FastAPI(title="DrHouseGPT API", lifespan=lifespan)

app.include_router(chat_router)
