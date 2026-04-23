import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("RUN_STARTUP_EVAL", "").strip().lower() in ("1", "true", "yes"):
        from .eval import run_startup_eval

        run_startup_eval()
    yield


app = FastAPI(title="DrHouseGPT API", lifespan=lifespan)

app.include_router(chat_router)
