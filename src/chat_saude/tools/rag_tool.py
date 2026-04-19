from chat_saude.observability.langfuse_client import end_span, start_span
from chat_saude.observability.logger import get_logger
from chat_saude.rag.pipeline import rag_answer_detailed

logger = get_logger(__name__)


def rag_tool(question: str):
    logger.info("RAG tool input: %s", question)
    span = start_span(name="rag_tool", input_payload={"question": question})
    try:
        details = rag_answer_detailed(question)
        end_span(
            span,
            output_payload={
                "response": details["answer"],
                "retrieval": details["retrieval"],
                "llm": details["llm"],
            },
        )
        return details["answer"]
    except Exception as exc:
        logger.exception("RAG tool failed")
        end_span(
            span,
            output_payload={"error": str(exc)},
            level="ERROR",
            status_message="rag_tool_error",
        )
        raise
