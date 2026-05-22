"""Unit tests for Langfuse client helpers and noop behavior."""

import importlib
import os
import sys
import urllib.error


def load_langfuse_client():
    sys.modules.pop("chat_saude.observability.langfuse_client", None)
    return importlib.import_module("chat_saude.observability.langfuse_client")


def test_resolve_langfuse_host_falls_back_to_base():
    """Falls back to the base URL when health checks fail."""
    langfuse_client = load_langfuse_client()

    def fail_urlopen(*args, **kwargs):
        raise urllib.error.URLError("nope")

    original_urlopen = langfuse_client.urllib.request.urlopen
    langfuse_client.urllib.request.urlopen = fail_urlopen
    try:
        assert langfuse_client._resolve_langfuse_host("http://example.com/") == "http://example.com"
    finally:
        langfuse_client.urllib.request.urlopen = original_urlopen


def test_get_langfuse_returns_noop_without_env():
    """Returns a noop client when env vars are missing."""
    langfuse_client = load_langfuse_client()

    langfuse_client._client = None

    old_env = {
        "LANGFUSE_PUBLIC_KEY": os.environ.pop("LANGFUSE_PUBLIC_KEY", None),
        "LANGFUSE_SECRET_KEY": os.environ.pop("LANGFUSE_SECRET_KEY", None),
        "LANGFUSE_HOST": os.environ.pop("LANGFUSE_HOST", None),
    }

    try:
        client = langfuse_client.get_langfuse()
        assert hasattr(client, "start_observation")
        span = langfuse_client.start_trace("test", {"message": "hello"})
        langfuse_client.end_span(span, output_payload={"ok": True})
        langfuse_client.finalize_trace({"done": True})
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
