"""
FastAPI router for the /chat endpoint.

This module wires the HTTP layer to ChatService, keeping routing thin:
it validates the incoming JSON body and delegates all business logic to
the service layer.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from chat_saude.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

# Single shared service instance — ChatService is stateless between requests.
chat_service = ChatService()


class ChatRequest(BaseModel):
    """Request body for the POST /chat/ endpoint."""

    message: str


@router.post("/")
def chat(req: ChatRequest):
    """Accept a user message and return the assistant response.

    Delegates to ``ChatService.handle_chat``, which runs the rules engine
    first (emergency detection, FAQ, domain check) and falls back to the
    LLM pipeline when the message passes all guards.
    """
    return chat_service.handle_chat(req.message)
