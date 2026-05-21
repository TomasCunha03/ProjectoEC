"""
FastAPI application entry point for the DrHouseGPT medical assistant API.

Registers the chat router and, when opted in via the ``RUN_STARTUP_EVAL``
environment variable, runs the pipeline evaluation suite before the server
begins accepting traffic.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from chat_saude.observability.logger import get_logger

from .chat import router as chat_router

logger = get_logger(__name__)


def _run_startup_eval_if_enabled() -> None:
    """Run the pipeline eval suite at boot if ``RUN_STARTUP_EVAL`` is truthy.

    A failure in the eval suite is non-fatal: the API still starts so that a
    partially broken deployment does not cause a complete outage. The warning
    logged here lets operators know something regressed without crashing the
    service.
    """
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
    """FastAPI lifespan context manager.

    Runs startup logic (eval, if enabled) before yielding control to the
    server, and can be extended with teardown logic after the yield.
    """
    _run_startup_eval_if_enabled()
    yield


app = FastAPI(title="DrHouseGPT API", lifespan=lifespan)

app.include_router(chat_router)
