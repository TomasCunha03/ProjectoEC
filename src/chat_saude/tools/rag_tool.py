from chat_saude.rag.pipeline import rag_answer
from chat_saude.observability.langfuse_client import end_span, start_span
from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

def rag_tool(question: str):
    logger.info("RAG tool input: %s", question)
    span = start_span(name="rag_tool", input_payload={"question": question})
    try:
        response = rag_answer(question)
        end_span(span, output_payload={"response": response})
        return response
    except Exception as exc:
        logger.exception("RAG tool failed")
        end_span(
            span,
            output_payload={"error": str(exc)},
            level="ERROR",
            status_message="rag_tool_error",
        )
        raise
