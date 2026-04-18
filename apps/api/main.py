from fastapi import FastAPI

from .chat import router as chat_router

app = FastAPI(title="DrHouseGPT API")


@app.get("/health")
def health():
    """Liveness/readiness for Docker and load balancers (loads after heavy imports complete)."""
    return {"status": "ok"}


app.include_router(chat_router)
