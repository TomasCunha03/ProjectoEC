import re
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
from chat_saude.tools.dashboard_tool import dashboard_tool
from chat_saude.tools.mongo_tool import mongo_query
from chat_saude.tools.rag_tool import rag_tool
from chat_saude.tools.sql_tool import sql_query

logger = get_logger(__name__)

# Detects explicit dashboard change requests without relying on the LLM.
# Matches "dashboard" + action verb, OR common filter phrases that imply
# the dashboard (e.g. "show chronic data for Texas", "filter to Portugal").
_DASHBOARD_KEYWORD_RE = re.compile(
    r"\bdashboard\b",
    re.IGNORECASE,
)
_DASHBOARD_ACTION_RE = re.compile(
    r"\b(show|filter|change|update|reset|set|display|view|clear)\b",
    re.IGNORECASE,
)
# Phrases that imply a dashboard filter even without the word "dashboard"
_DASHBOARD_IMPLICIT_RE = re.compile(
    r"\b("
    r"chronic\s+(data|disease|diseases|section)"
    r"|filter\s+(chronic|global|to|by)"
    r"|show\s+(chronic|global|me\s+(data\s+for|.*\s+data\s+on))"
    r"|show\s+data\s+for"
    r"|immunization\s+(data|trend|section|filter|window)"
    r"|filter\s+immunization"
    r"|vaccine\s+(data|trend|filter|window|code)"
    r"|show\s+immunization"
    r"|BCG|DTP3|MCV1|HEPB|POL3"
    r")\b",
    re.IGNORECASE,
)


def _is_dashboard_request(message: str) -> bool:
    has_action = bool(_DASHBOARD_ACTION_RE.search(message))
    if bool(_DASHBOARD_KEYWORD_RE.search(message)) and has_action:
        return True
    return bool(_DASHBOARD_IMPLICIT_RE.search(message)) and has_action


class ChatService:
    """Orchestrates chat: rules, tool selection, and tool execution."""

    def handle_chat(self, message: str) -> dict:
        t_start = time.perf_counter()
        logger.info("Incoming chat message: %s", message)
        start_trace(name="chat_request", input_payload={"message": message})

        try:
            # Fast-path: detect dashboard requests BEFORE rules.
            # Domain validation rejects these as low-similarity; skip it entirely.
            if _is_dashboard_request(message):
                logger.info("Dashboard request detected by keyword matcher")
                dash_span = start_span(name="dashboard", input_payload={"message": message})
                reply, dashboard_filters = dashboard_tool(message)
                end_span(
                    dash_span,
                    output_payload={"reply": reply, "filters": dashboard_filters},
                )
                elapsed = time.perf_counter() - t_start
                logger.info(
                    "Chat response in %.2fs tool_used=dashboard filters=%s",
                    elapsed,
                    dashboard_filters,
                )
                result = {
                    "response": reply,
                    "tool_used": "dashboard_query",
                    "dashboard_filters": dashboard_filters,
                }
                finalize_trace(output_payload=result)
                return result

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

            # Handle DASHBOARD tool separately (returns filters, not just text)
            if "dashboard_query" in selected_tools:
                dash_span = start_span(name="dashboard", input_payload={"message": message})
                reply, dashboard_filters = dashboard_tool(message)
                end_span(
                    dash_span,
                    output_payload={"reply": reply, "filters": dashboard_filters},
                )
                elapsed = time.perf_counter() - t_start
                logger.info(
                    "Chat response in %.2fs tool_used=dashboard filters=%s",
                    elapsed,
                    dashboard_filters,
                )
                result = {
                    "response": reply,
                    "tool_used": "dashboard_query",
                    "dashboard_filters": dashboard_filters,
                }
                finalize_trace(output_payload=result)
                return result

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
