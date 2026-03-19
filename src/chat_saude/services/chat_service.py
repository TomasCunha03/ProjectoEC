from api.rules import apply_rules
from agents.tool_selection_agent import select_tool
from chat_saude.observability.langfuse_client import end_span, finalize_trace, start_span, start_trace
from chat_saude.observability.logger import get_logger
from chat_saude.tools.mongo_tool import mongo_query
from chat_saude.tools.rag_tool import rag_tool
from chat_saude.tools.sql_tool import sql_query

logger = get_logger(__name__)


class ChatService:
    """Orchestrates chat: rules, tool selection, and tool execution."""

    def handle_chat(self, message: str) -> dict:
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

            tool_selection_span = start_span(name="tool_selection", input_payload={"message": message})
            decision = select_tool(message)
            end_span(tool_selection_span, output_payload={"decision": decision})
            tool = decision["tool"]

            if tool == "rag_answer":
                tool_span = start_span(name="rag", input_payload={"message": message})
                reply = rag_tool(message)
                end_span(tool_span, output_payload={"reply": reply})
            elif tool == "sql_query":
                tool_span = start_span(name="sql", input_payload={"message": message})
                reply = sql_query(message)
                end_span(tool_span, output_payload={"reply": reply})
            elif tool == "mongo_query":
                tool_span = start_span(name="mongo", input_payload={"message": message})
                reply = mongo_query(message)
                end_span(tool_span, output_payload={"reply": reply})
            elif tool == "both":
                rag_span = start_span(name="rag", input_payload={"message": message})
                rag_reply = rag_tool(message)
                end_span(rag_span, output_payload={"reply": rag_reply})

                sql_span = start_span(name="sql", input_payload={"message": message})
                sql_reply = sql_query(message)
                end_span(sql_span, output_payload={"reply": sql_reply})

                reply = f"Resposta RAG:\n{rag_reply}\n\nResposta SQL:\n{sql_reply}"
            else:
                reply = "Desculpe, não consigo responder a essa pergunta."

            result = {"response": reply, "tool_used": tool or "none"}
            finalize_trace(output_payload=result)
            return result
        except Exception as exc:
            logger.exception("Chat service failed")
            finalize_trace(output_payload={"error": str(exc), "status": "chat_service_error"})
            raise
