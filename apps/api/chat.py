from fastapi import APIRouter
from pydantic import BaseModel

from chat_saude.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

chat_service = ChatService()


class ChatRequest(BaseModel):
    message: str


@router.post("/")
def chat(req: ChatRequest):
    return chat_service.handle_chat(req.message)
