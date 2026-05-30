"""
Langfuse observability client module.

Wraps the Langfuse SDK so that:
  - When credentials are missing or the SDK is not installed, every call silently
    becomes a no-op; callers never need to guard against ``None``.
  - The active trace and current parent span are stored in ``ContextVar`` so
    concurrent async/threaded requests each maintain their own observation chain.
  - The correct Langfuse host is discovered at startup by probing known URLs,
    handling both Docker Compose service-name DNS and localhost access.
"""

import os
import urllib.error
import urllib.request
from contextvars import ContextVar


class _NoOpEntity:
    """Null-object replacement for a real Langfuse trace or span.

    Returned whenever Langfuse is unavailable so callers can use the same
    start/update/end API without any conditional checks.
    """

    def start_observation(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def end(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None

    def update(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


# Per-request state stored in context variables so concurrent requests don't
# share trace/span references across threads or async tasks.
_current_trace: ContextVar[object | None] = ContextVar("current_langfuse_trace", default=None)
_current_parent_span: ContextVar[object | None] = ContextVar("current_langfuse_parent_span", default=None)

# Module-level singletons — initialised lazily on first use.
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
    """Return the module-level Langfuse client, creating it on the first call.

    Falls back to the no-op singleton when credentials are absent or the SDK
    import fails, ensuring callers always receive a usable object.
    """
    global _client
    if _client is not None:
        return _client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")

    if not public_key or not secret_key or not host:
        # Langfuse is not configured — degrade silently.
        _client = _noop
        return _client

    try:
        from langfuse import Langfuse

        global _resolved_host
        if _resolved_host is None:
            # Probe once and cache the reachable host URL for subsequent calls.
            _resolved_host = _resolve_langfuse_host(host)
        _client = Langfuse(public_key=public_key, secret_key=secret_key, host=_resolved_host)
    except Exception:
        # SDK not installed or instantiation failed — degrade silently.
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
    """Open a child span nested under the current parent span (or the root trace).

    The new span is stored as the current parent so that subsequent calls to
    ``start_span`` nest correctly within the same request context.
    """
    parent = _current_parent_span.get()
    trace = _current_trace.get()
    # Prefer the innermost open span; fall back to the root trace, then the client.
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


def end_span(span, output_payload: object = None, level: str | None = None, status_message: str | None = None):
    """Close a span and record optional output, severity level, and status message.

    ``level`` and ``status_message`` are used to surface errors in the Langfuse
    UI without raising exceptions in the caller.  The current parent span is
    cleared so the context returns to the root trace after this span closes.
    """
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
    """Close the root trace for the current request and clear all context vars.

    Must be called exactly once per request — both on the happy path and in
    error handlers — to ensure the trace is flushed to Langfuse and the
    context variables don't leak into the next request on the same thread.
    """
    trace = _current_trace.get()
    try:
        if output_payload is not None:
            trace.update(output=output_payload)
        trace.end()
    except Exception:
        pass
    finally:
        # Always clear context so stale spans cannot bleed into the next request.
        _current_trace.set(None)
        _current_parent_span.set(None)
