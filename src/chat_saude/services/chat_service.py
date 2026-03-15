from api.rules import apply_rules
from agents.tool_selection_agent import select_tool
from chat_saude.tools.mongo_tool import mongo_query
from chat_saude.tools.rag_tool import rag_tool
from chat_saude.tools.sql_tool import sql_query


class ChatService:
    """Orchestrates chat: rules, tool selection, and tool execution."""

    def handle_chat(self, message: str) -> dict:
        rule_response = apply_rules(message)
        if rule_response:
            return {"response": rule_response, "tool_used": "rules"}

        decision = select_tool(message)
        tool = decision["tool"]

        if tool == "rag_answer":
            reply = rag_tool(message)
        elif tool == "sql_query":
            reply = sql_query(message)
        elif tool == "mongo_query":
            reply = mongo_query(message)
        elif tool == "both":
            rag_reply = rag_tool(message)
            sql_reply = sql_query(message)
            reply = f"Resposta RAG:\n{rag_reply}\n\nResposta SQL:\n{sql_reply}"
        else:
            reply = "Desculpe, não consigo responder a essa pergunta."

        return {"response": reply, "tool_used": tool or "none"}
