import os
import urllib.error
import urllib.request
from contextvars import ContextVar


class _NoOpEntity:
    def start_observation(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def end(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    def update(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


_current_trace: ContextVar[object | None] = ContextVar("current_langfuse_trace", default=None)
_current_parent_span: ContextVar[object | None] = ContextVar(
    "current_langfuse_parent_span", default=None
)

_client = None
_noop = _NoOpEntity()
_resolved_host: str | None = None


def _resolve_langfuse_host(host: str) -> str:
    """Pick a reachable Langfuse base URL (Compose DNS vs localhost on the host)."""

    base = host.rstrip("/")
    candidates: list[str] = []
    seen: set[str] = set()
    for url in (base, "http://localhost:3000", "http://127.0.0.1:3000"):
        if url and url not in seen:
            seen.add(url)
            candidates.append(url)

    for url in candidates:
        try:
            urllib.request.urlopen(f"{url}/api/public/health", timeout=2)
            return url
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return base


def get_langfuse():
    global _client
    if _client is not None:
        return _client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")

    if not public_key or not secret_key or not host:
        _client = _noop
        return _client

    try:
        from langfuse import Langfuse

        global _resolved_host
        if _resolved_host is None:
            _resolved_host = _resolve_langfuse_host(host)
        _client = Langfuse(public_key=public_key, secret_key=secret_key, host=_resolved_host)
    except Exception:
        _client = _noop

    return _client


def start_trace(name: str, input_payload: object):
    """
    Start a root Langfuse observation (a "span") for the current request.

    Langfuse SDK v4 uses start_observation()/update()/end() (not client.trace()).
    """
    client = get_langfuse()
    try:
        root_span = client.start_observation(
            name=name,
            as_type="span",
            input=input_payload,
        )
    except Exception:
        root_span = _noop

    _current_trace.set(root_span)
    _current_parent_span.set(None)
    return root_span


def start_span(name: str, input_payload: object = None):
    parent = _current_parent_span.get()
    trace = _current_trace.get()
    entity = parent or trace or get_langfuse()

    try:
        if input_payload is None:
            span = entity.start_observation(name=name, as_type="span")
        else:
            span = entity.start_observation(name=name, as_type="span", input=input_payload)
    except Exception:
        span = _noop

    _current_parent_span.set(span)
    return span


def end_span(
    span, output_payload: object = None, level: str | None = None, status_message: str | None = None
):
    try:
        update_kwargs: dict = {}
        if output_payload is not None:
            update_kwargs["output"] = output_payload
        if level is not None:
            update_kwargs["level"] = level
        if status_message is not None:
            update_kwargs["status_message"] = status_message

        # update() then end() is the v4 lifecycle for manually created observations.
        if update_kwargs:
            span.update(**update_kwargs)
        else:
            span.update()

        span.end()
    except Exception:
        pass
    finally:
        _current_parent_span.set(None)


def finalize_trace(output_payload: object = None):
    trace = _current_trace.get()
    try:
        if output_payload is not None:
            trace.update(output=output_payload)
        trace.end()
    except Exception:
        pass
    finally:
        _current_trace.set(None)
        _current_parent_span.set(None)
