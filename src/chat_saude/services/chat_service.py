from urllib import response

from ollama import Client
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
client = Client(host="http://ollama:11434")

class ChatService:
    """Orchestrates chat: rules, tool selection, and tool execution."""
    def _handle_errors(self, errors: list[str], message: str) -> str:
        return (
        "I was unable to provide a complete answer with the information available."
        "Can you provide more information or reformulate the question? "
        "That way I can help you better."
    )

    def _build_final_answer(self, user_message: str, raw_tool_output: str) -> str:
        prompt = f"""
        You are a professional medical assistant.

        The user asked:
        "{user_message}"

        You have the following information from internal systems:
        {raw_tool_output}

        RULES:
        - NEVER mention tool names (RAG, SQL, Mongo)
        - ALWAYS respond in natural, human-friendly language
        - Combine information from multiple sources into one answer

        Write a clear, natural, and user-friendly answer.
        """

        try:
            response = requests.post(
                "http://ollama:11434/api/generate",
                json={
                    "model": "llama3", 
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )

            return response.json().get("response", raw_tool_output)

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return raw_tool_output
    
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

            tool_selection_span = start_span(
                name="tool_selection", input_payload={"message": message}
            )
            decision = select_tool(message)
            end_span(tool_selection_span, output_payload={"decision": decision})

            selected_tools = decision.get("tools") or []
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
                try:
                    replies_by_tool[tool] = tool_to_fn[tool](message)
                except Exception as e:
                    replies_by_tool[tool] = f"ERROR: {str(e)}"
                end_span(tool_span, output_payload={"reply": replies_by_tool[tool]})
            # NOVO BLOCO — DETETAR ERROS
            errors = [
                r for r in replies_by_tool.values()
                if isinstance(r, str) and r.startswith("ERROR")
            ]

#  SE HOUVER ERROS → PARAR AQUI
            if errors:
                reply = self._handle_errors(errors, message)

#  CASO NÃO HAJA ERROS → fluxo normal
            elif not ordered_tools:
                reply = "Sorry, I cannot answer that question."

            elif len(ordered_tools) == 1:
                reply = replies_by_tool[ordered_tools[0]]

            elif len(ordered_tools) > 1:
                combined = "\n".join(replies_by_tool.values())
                reply = self._build_final_answer(message, combined)


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