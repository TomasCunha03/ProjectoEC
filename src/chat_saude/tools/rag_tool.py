"""
RAG tool for the chat_saude agent.

Thin wrapper around the RAG pipeline that adds observability (Langfuse span
tracing and structured logging).  The retrieval and generation logic lives in
chat_saude.rag.pipeline; this module only handles the agent tool interface.
"""

from chat_saude.observability.langfuse_client import end_span, start_span
from chat_saude.observability.logger import get_logger
from chat_saude.rag.pipeline import rag_answer

logger = get_logger(__name__)


def rag_tool(question: str):
    """Answer a question using the RAG (Retrieval-Augmented Generation) pipeline.

    Delegates to rag_answer, which retrieves relevant document chunks from the
    vector store and uses them to ground the LLM response.  Exceptions are
    logged and recorded in the observability span before being re-raised so the
    agent orchestrator can handle them appropriately.

    Args:
        question: The natural-language question from the user.

    Returns:
        The generated answer string from the RAG pipeline.
    """
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
