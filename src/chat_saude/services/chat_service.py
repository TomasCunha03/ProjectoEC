import os
import re
import time

import ollama
import yaml

from api.canned import canned_text, validate_query

from agents.conversation_router import route_conversation
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

_AGENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agents"))
_PROMPTS_PATH = os.path.join(_AGENTS_DIR, "prompts.yaml")


def _strip_links_for_user(text: str) -> str:
    """Remove URLs and markdown links from text shown to the user (safety net)."""
    if not text:
        return text
    # [label](url) → keep label only when URL looks like http(s)
    text = re.sub(r"\[([^\]]*)\]\(\s*https?://[^)]+\)", r"\1", text, flags=re.I)
    # Bare http(s) URLs
    text = re.sub(r"https?://[^\s\)\]>'\"]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


# When retrieval is thin, the model may return a few generic sentences; nudge the user to go further.
_SHORT_TOOL_ANSWER_MAX_CHARS = 500
_SHORT_TOOL_ANSWER_MAX_WORDS = 75
_BRIEF_COVERAGE_SUFFIX = (
    "\n\nThis is as much as I can say with confidence from the information I was able to use here. "
    "If you need a fuller or more detailed answer, I suggest other trusted medical resources or a "
    "healthcare professional."
)


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _append_brief_coverage_hint_if_applicable(reply: str) -> str:
    """If the tool answer is very short, add a line that the user may need to look elsewhere."""
    s = (reply or "").strip()
    if not s:
        return s
    if _BRIEF_COVERAGE_SUFFIX.strip() in s:
        return reply
    if "I couldn't assemble a clear answer" in s:
        return reply
    if len(s) > _SHORT_TOOL_ANSWER_MAX_CHARS or _word_count(s) > _SHORT_TOOL_ANSWER_MAX_WORDS:
        return reply
    return s + _BRIEF_COVERAGE_SUFFIX


def _load_multi_tool_synthesis_template() -> str:
    try:
        with open(_PROMPTS_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return (data.get("multi_tool_synthesis_prompt") or "").strip()
    except OSError as exc:
        logger.warning("Could not load multi_tool_synthesis_prompt: %s", exc)
        return ""

def _synthesize_multi_tool_reply(
    user_message: str, ordered_tools: list[str], replies_by_tool: dict[str, str]
) -> str:
    """Merge multiple tool outputs into one user-facing answer (no tool labels)."""
    blocks: list[str] = []
    for i, tool in enumerate(ordered_tools, start=1):
        text = (replies_by_tool.get(tool) or "").strip()
        if text:
            blocks.append(f"[Information block {i}]\n{text}")

    if not blocks:
        return (
            "I couldn't assemble a clear answer from the retrieved material. "
            "Try rephrasing your question, or speak with a clinician for personal advice."
        )

    if len(blocks) == 1:
        only = blocks[0]
        if only.startswith("[Information block ") and "\n" in only:
            return only.split("\n", 1)[1].strip()
        return only.strip()

    drafts = "\n\n".join(blocks)
    template = _load_multi_tool_synthesis_template()

    if not template:
        logger.warning("multi_tool_synthesis_prompt empty; joining tool text without synthesis")
        return "\n\n".join(
            (replies_by_tool.get(t) or "").strip()
            for t in ordered_tools
            if (replies_by_tool.get(t) or "").strip()
        )

    # Avoid str.format — drafts may contain "{" / "}".
    prompt = template.replace("{question}", user_message).replace("{drafts}", drafts)
    host = os.getenv("OLLAMA_HOST", "http://ollama:11434").rstrip("/")
    model = os.getenv("LLM_MODEL", "gemma3:1b")

    try:
        client = ollama.Client(host=host)
        response = client.generate(
            model=model,
            prompt=prompt,
            options={"temperature": 0.2},
        )
        out = (response.get("response") or "").strip()
        if out:
            return out
    
    except Exception:
        logger.exception("Multi-tool synthesis LLM call failed")
    
    return "\n\n".join(
        (replies_by_tool.get(t) or "").strip()
        for t in ordered_tools
        if (replies_by_tool.get(t) or "").strip()
    )


class ChatService:
    """Orchestrates chat: short validation, one router LLM call, then tool execution."""

    def handle_chat(self, message: str) -> dict:
        t_start = time.perf_counter()
        logger.info("Incoming chat message: %s", message)
        start_trace(name="chat_request", input_payload={"message": message})

        try:
            short = validate_query(message)
            if short:
                result = {"response": short, "tool_used": "rules"}
                finalize_trace(output_payload=result)
                return result

            router_span = start_span(name="conversation_router", input_payload={"message": message})
            route = route_conversation(message)
            end_span(router_span, output_payload={"route": route.__dict__})

            if route.mode == "direct":
                text = canned_text(route.canned_key)
                result = {"response": text, "tool_used": "router"}
                finalize_trace(output_payload=result)
                return result

            ordered_tools = [
                t for t in ["rag_answer", "sql_query", "mongo_query"] if t in route.tools
            ]
            logger.info("Router tools: %s", ordered_tools)

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
                reply = (
                    "I'm not sure how to answer that yet. Could you rephrase as a clear question "
                    "(for example about a symptom, a condition, or health statistics)?"
                )
            elif len(ordered_tools) == 1:
                reply = replies_by_tool[ordered_tools[0]]
            else:
                synth_span = start_span(
                    name="multi_tool_synthesis",
                    input_payload={"message": message, "tools": ordered_tools},
                )
                reply = _synthesize_multi_tool_reply(message, ordered_tools, replies_by_tool)
                end_span(synth_span, output_payload={"reply_preview": reply[:2500]})

            if ordered_tools:
                reply = _strip_links_for_user(reply)
                reply = _append_brief_coverage_hint_if_applicable(reply)

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
