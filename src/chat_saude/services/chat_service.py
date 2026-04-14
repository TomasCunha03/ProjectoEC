import time

from api.rules import apply_rules

from agents.tool_selection_agent import select_tool
from chat_saude.observability.langfuse_client import (
    end_span,
    finalize_trace,
    start_span,
    start_trace,
)
from chat_saude.observability.logger import get_logger
from chat_saude.tools.mongo_tool import mongo_query
from chat_saude.tools.rag_tool import rag_tool
from chat_saude.tools.sql_tool import sql_query

logger = get_logger(__name__)


class ChatService:
    """Orchestrates chat: rules, tool selection, and tool execution."""

    def handle_chat(self, message: str) -> dict:
        t_start = time.perf_counter()
        logger.info("Incoming chat message: %s", message)
        start_trace(name="chat_request", input_payload={"message": message})

        try:
            rules_span = start_span(name="rules", input_payload={"message": message})
            rule_response = apply_rules(message)
            end_span(rules_span, output_payload={"rule_response": rule_response})

            if rule_response:
                result = {"response": rule_response, "tool_used": "rules"}
                finalize_trace(output_payload=result)
                return result

            tool_selection_span = start_span(
                name="tool_selection", input_payload={"message": message}
            )
            decision = select_tool(message)
            end_span(tool_selection_span, output_payload={"decision": decision})

            selected_tools = decision.get("tools") or []
            logger.info("Tools selected: %s", selected_tools)
            ordered_tools = [
                t for t in ["rag_answer", "sql_query", "mongo_query"] if t in selected_tools
            ]

            tool_to_span = {
                "rag_answer": "rag",
                "sql_query": "sql",
                "mongo_query": "mongo",
            }
            tool_to_fn = {
                "rag_answer": rag_tool,
                "sql_query": sql_query,
                "mongo_query": mongo_query,
            }

            replies_by_tool: dict[str, str] = {}
            for tool in ordered_tools:
                tool_span = start_span(name=tool_to_span[tool], input_payload={"message": message})
                replies_by_tool[tool] = tool_to_fn[tool](message)
                end_span(tool_span, output_payload={"reply": replies_by_tool[tool]})

            if not ordered_tools:
                reply = "Sorry, I cannot answer that question."
            elif len(ordered_tools) == 1:
                reply = replies_by_tool[ordered_tools[0]]
            else:
                parts = []
                for tool in ordered_tools:
                    if tool == "rag_answer":
                        parts.append(f"RAG answer:\n{replies_by_tool[tool]}")
                    elif tool == "sql_query":
                        parts.append(f"SQL answer:\n{replies_by_tool[tool]}")
                    elif tool == "mongo_query":
                        parts.append(f"Mongo answer:\n{replies_by_tool[tool]}")
                reply = "\n\n".join(parts)

            elapsed = time.perf_counter() - t_start
            logger.info(
                "Chat response in %.2fs tool_used=%s",
                elapsed,
                ",".join(ordered_tools) if ordered_tools else "none",
            )
            result = {
                "response": reply,
                "tool_used": ",".join(ordered_tools) if ordered_tools else "none",
            }
            finalize_trace(output_payload=result)
            return result
        except Exception as exc:
            logger.exception("Chat service failed")
            finalize_trace(output_payload={"error": str(exc), "status": "chat_service_error"})
            raise
