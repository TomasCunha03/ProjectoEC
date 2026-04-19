import concurrent.futures
import os
from contextvars import ContextVar
from typing import Any

from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)


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


def _langfuse_sync_timeout_seconds() -> float:
    raw = os.getenv("LANGFUSE_SYNC_TIMEOUT_SECONDS", "8")
    try:
        return max(0.5, float(raw))
    except ValueError:
        return 8.0


def _truncate_for_langfuse(obj: Any, max_chars: int = 16000) -> Any:
    """Keep Langfuse payloads small so export HTTP calls cannot stall on huge bodies."""
    if isinstance(obj, str):
        if len(obj) <= max_chars:
            return obj
        return obj[:max_chars] + f"... [truncated, total {len(obj)} chars]"
    if isinstance(obj, dict):
        return {k: _truncate_for_langfuse(v, max_chars) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate_for_langfuse(v, max_chars) for v in obj]
    return obj


def _run_langfuse_bounded(fn) -> None:
    """Langfuse SDK flushes over HTTP synchronously; never block the API beyond a short cap."""
    timeout = _langfuse_sync_timeout_seconds()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning(
            "Langfuse operation exceeded %.1fs (set LANGFUSE_SYNC_TIMEOUT_SECONDS); abandoning sync flush.",
            timeout,
        )
    except Exception:
        pass
    finally:
        # wait=False: do not block here if Langfuse HTTP is stuck (executor context manager would wait forever).
        executor.shutdown(wait=False)


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

        _client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
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


def tracing_active() -> bool:
    """True when a non-noop root trace was started (safe to add child spans, e.g. RAG substeps)."""
    t = _current_trace.get()
    return t is not None and not isinstance(t, _NoOpEntity)


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
        if isinstance(span, _NoOpEntity):
            return

        update_kwargs: dict = {}
        if output_payload is not None:
            update_kwargs["output"] = _truncate_for_langfuse(output_payload)
        if level is not None:
            update_kwargs["level"] = level
        if status_message is not None:
            update_kwargs["status_message"] = status_message

        def _finish() -> None:
            if update_kwargs:
                span.update(**update_kwargs)
            else:
                span.update()
            span.end()

        _run_langfuse_bounded(_finish)
    except Exception:
        pass
    finally:
        _current_parent_span.set(None)


def finalize_trace(output_payload: object = None):
    trace = _current_trace.get()
    _current_trace.set(None)
    _current_parent_span.set(None)

    if trace is None or isinstance(trace, _NoOpEntity):
        return

    payload = _truncate_for_langfuse(output_payload) if output_payload is not None else None

    def _finish() -> None:
        try:
            if payload is not None:
                trace.update(output=payload)
            else:
                trace.update()
            trace.end()
        except Exception:
            pass

    _run_langfuse_bounded(_finish)
