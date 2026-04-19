"""
Legacy shim: pre-LLM validation only.

All routing and tool choice happens in ``agents.conversation_router`` (single structured LLM call).
Fixed reply text lives in ``api.canned``.
"""

from api.canned import canned_text, validate_query

__all__ = ["apply_rules", "canned_text", "validate_query"]


def apply_rules(query: str):
    """Return an early user-visible string only if the message is too short; else None."""
    return validate_query(query)
