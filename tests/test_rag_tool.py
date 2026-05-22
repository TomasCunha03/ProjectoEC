"""Unit tests for the RAG tool wrapper and span behavior."""

import importlib
import sys
import types

import pytest


def load_rag_tool(*, rag_answer=None, start_span=None, end_span=None):
    obs_mod = types.ModuleType("chat_saude.observability.langfuse_client")
    obs_mod.start_span = start_span or (lambda *args, **kwargs: object())
    obs_mod.end_span = end_span or (lambda *args, **kwargs: None)
    sys.modules["chat_saude.observability.langfuse_client"] = obs_mod

    rag_mod = types.ModuleType("chat_saude.rag.pipeline")
    rag_mod.rag_answer = rag_answer or (lambda question: "ok")
    sys.modules["chat_saude.rag.pipeline"] = rag_mod

    sys.modules.pop("chat_saude.tools.rag_tool", None)
    return importlib.import_module("chat_saude.tools.rag_tool")


def test_rag_tool_happy_path_records_span():
    """Records spans and returns the RAG answer on success."""
    calls = []

    def start_span(name, input_payload=None):
        calls.append(("start", name, input_payload))
        return "span"

    def end_span(span, output_payload=None, level=None, status_message=None):
        calls.append(("end", span, output_payload, level, status_message))

    rag_tool = load_rag_tool(
        rag_answer=lambda question: "answer",
        start_span=start_span,
        end_span=end_span,
    )

    result = rag_tool.rag_tool("hello")

    assert result == "answer"
    assert calls[0][0] == "start"
    assert calls[1][0] == "end"
    assert calls[1][2] == {"response": "answer"}


def test_rag_tool_propagates_error_and_logs():
    """Propagates errors while marking the span as failed."""
    calls = []

    def end_span(span, output_payload=None, level=None, status_message=None):
        calls.append((output_payload, level, status_message))

    rag_tool = load_rag_tool(
        rag_answer=lambda question: (_ for _ in ()).throw(RuntimeError("boom")),
        end_span=end_span,
    )

    with pytest.raises(RuntimeError):
        rag_tool.rag_tool("hello")

    assert calls
    assert calls[0][1] == "ERROR"
    assert calls[0][2] == "rag_tool_error"
