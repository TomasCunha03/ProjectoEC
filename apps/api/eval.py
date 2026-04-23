"""
Startup / manual evaluation of the chat pipeline (rules engine + tool routing).

Run manually (from project root, with PYTHONPATH including src):
  PYTHONPATH=apps:src python -m api.eval

If ``OLLAMA_HOST`` points at ``http://ollama:11434`` (Compose) but you run this script on
the host, eval probes ``127.0.0.1:11434`` / ``localhost`` and sets ``OLLAMA_HOST`` for the
process when one of them responds. Inside containers, the first successful URL wins.

Output is printed and also written to EVAL_REPORT_PATH (default: eval_report.txt in cwd).

Or enable on API boot with RUN_STARTUP_EVAL=1 (see main.py).
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Literal, TextIO

from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class EvalCase:
    id: str
    capability: str
    message: str
    """If 'rules', tool_used must equal 'rules'. Otherwise, this tool id must appear in tool_used."""

    expected_tool: str
    response_hint: str
    """Lowercase substring expected in response (rules and tools)."""

    kind: Literal["rules", "tool"] = "tool"


def _cases() -> list[EvalCase]:
    """~10 prompts covering rules (incl. safety, FAQ, domain) and each data tool."""

    return [
        EvalCase(
            id="rules_too_short",
            capability="rules / validation",
            message="no",
            expected_tool="rules",
            response_hint="valid question",
            kind="rules",
        ),
        EvalCase(
            id="rules_emergency",
            capability="rules / urgency",
            message="I can't breathe and I have severe crushing chest pain right now.",
            expected_tool="rules",
            response_hint="emergency",
            kind="rules",
        ),
        EvalCase(
            id="rules_identity",
            capability="rules / FAQ — identity",
            message="Hello, who are you and what should I call you?",
            expected_tool="rules",
            response_hint="drhousegpt",
            kind="rules",
        ),
        # Short phrase only: compound questions often miss FAQ cosine threshold & hit tool selection.
        EvalCase(
            id="rules_capabilities",
            capability="rules / FAQ — what do you do",
            message="What do you do?",
            expected_tool="rules",
            response_hint="diagnos",
            kind="rules",
        ),
        EvalCase(
            id="rules_non_medical",
            capability="rules / off-topic (stupid question)",
            message="Who won the Super Bowl last year and what was the final score?",
            expected_tool="rules",
            response_hint="medical assistant",
            kind="rules",
        ),
        EvalCase(
            id="rules_gibberish",
            capability="rules / low-signal nonsense",
            message="asdf qwerty zxcv nonsense lorem ipsum foo",
            expected_tool="rules",
            response_hint="not quite sure",
            kind="rules",
        ),
        EvalCase(
            id="tool_mongo_who",
            capability="mongo — WHO / indicators",
            message=(
                "Which WHO Global Health Observatory indicators or indicator codes "
                "mention tuberculosis or TB?"
            ),
            expected_tool="mongo_query",
            response_hint="",
            kind="tool",
        ),
        EvalCase(
            id="tool_mongo_disease",
            capability="mongo — MedlinePlus-style disease summary",
            message="What is hypertension, what causes it, and what are common symptoms?",
            expected_tool="mongo_query",
            response_hint="",
            kind="tool",
        ),
        EvalCase(
            id="tool_sql_stats",
            capability="sql — structured stats / facts",
            message=(
                "Using your SQL health database, how many distinct diseases are recorded, "
                "and list three disease names from the diseases table."
            ),
            expected_tool="sql_query",
            response_hint="",
            kind="tool",
        ),
        EvalCase(
            id="tool_rag_chroma",
            capability="rag / chroma — literature & mechanisms",
            message=(
                "Explain the pathophysiological mechanisms of insulin resistance and why "
                "physical activity improves glycemic control, based on scientific literature."
            ),
            expected_tool="rag_answer",
            response_hint="",
            kind="tool",
        ),
    ]


def _tool_matches(actual: str, expected: str, kind: Literal["rules", "tool"]) -> bool:
    actual = (actual or "").strip()
    if kind == "rules":
        return actual == "rules"
    parts = [p.strip() for p in actual.split(",") if p.strip()]
    return expected in parts


def _response_ok(text: str, hint: str) -> bool:
    if not hint:
        return bool(text and str(text).strip())
    return hint.lower() in (text or "").lower()


def _effective_ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", "http://ollama:11434")


def _ensure_ollama_url_for_process() -> bool:
    """Try configured URL then localhost fallbacks; set ``OLLAMA_HOST`` if one responds."""
    import ollama

    configured = (os.getenv("OLLAMA_HOST") or "").strip() or "http://ollama:11434"
    prior = os.environ.get("OLLAMA_HOST")

    candidates: list[str] = []
    seen: set[str] = set()
    for url in (
        configured,
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://ollama:11434",
    ):
        if url and url not in seen:
            seen.add(url)
            candidates.append(url)

    for url in candidates:
        try:
            ollama.Client(host=url).list()
            os.environ["OLLAMA_HOST"] = url
            if prior != url:
                logger.info(
                    "OLLAMA_HOST set to %s for this process (was %r)",
                    url,
                    prior if prior is not None else configured,
                )
            return True
        except Exception:
            continue

    logger.warning(
        "Ollama not reachable at any of: %s — tool eval cases will be skipped",
        ", ".join(candidates),
    )
    return False


def _emit(line: str, report: TextIO | None) -> None:
    print(line)
    if report is not None:
        report.write(line + "\n")
        report.flush()


def run_startup_eval(report_path: str | None = None) -> bool:
    """Runs all eval cases; logs a summary. Returns True if none failed (skipped ok).

    Writes the same lines as stdout to ``report_path``. If omitted, uses env
    ``EVAL_REPORT_PATH`` (default ``eval_report.txt``). Set ``EVAL_REPORT_PATH``
    to empty or ``none`` to disable file output.
    """

    ollama_ok = _ensure_ollama_url_for_process()

    # Lazy import so importing this module does not load the full chat stack until URL is chosen.
    from chat_saude.services.chat_service import ChatService

    path_env = os.getenv("EVAL_REPORT_PATH")
    if report_path is None:
        if path_env is None:
            report_path_resolved = os.path.abspath("eval_report.txt")
        else:
            p = path_env.strip().lower()
            report_path_resolved = None if p in ("", "none", "0", "false") else path_env.strip()
    else:
        report_path_resolved = report_path

    report_file: TextIO | None = None
    if report_path_resolved:
        report_file = open(report_path_resolved, "w", encoding="utf-8")

    strict_tools = os.getenv("EVAL_REQUIRE_OLLAMA", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    cases = _cases()
    service = ChatService()
    passed = 0
    failed: list[str] = []
    skipped: list[str] = []

    def emit(line: str = "") -> None:
        _emit(line, report_file)

    emit(f"\n=== DrHouseGPT startup eval ({len(cases)} cases) ===")
    if report_path_resolved:
        emit(f"(report file: {report_path_resolved})")
    emit(f"(OLLAMA_HOST={_effective_ollama_host()})")
    emit()

    logger.info("Startup eval: running %d cases", len(cases))

    for case in cases:
        if case.kind == "tool" and not ollama_ok:
            if strict_tools:
                emit(
                    f"[FAIL] {case.id} ({case.capability}) — "
                    "Ollama unreachable (EVAL_REQUIRE_OLLAMA=1)"
                )
                failed.append(case.id)
                continue
            skipped.append(case.id)
            emit(f"[SKIP] {case.id} ({case.capability}) — Ollama unreachable")
            continue

        t0 = time.perf_counter()
        err: str | None = None
        tool_used = ""
        try:
            out = service.handle_chat(case.message)
            tool_used = str(out.get("tool_used") or "")
            response = str(out.get("response") or "")
            dt = time.perf_counter() - t0

            if not _tool_matches(tool_used, case.expected_tool, case.kind):
                err = (
                    f"tool_used={tool_used!r}, want {case.kind} "
                    f"({case.expected_tool!r})"
                )
            elif not _response_ok(response, case.response_hint):
                err = f"response missing hint {case.response_hint!r}"
        except Exception as exc:
            dt = time.perf_counter() - t0
            err = f"exception: {exc}"
            logger.exception("Eval case %s failed", case.id)

        if err:
            failed.append(case.id)
            status = "FAIL"
            detail = err
        else:
            passed += 1
            status = "ok"
            detail = "rules" if case.kind == "rules" else f"tool_used={tool_used}"

        emit(
            f"[{status}] {case.id} ({case.capability}) "
            f"{dt:.1f}s — {detail}"
        )

    summary = (
        f"\n=== Summary: {passed}/{len(cases)} passed"
        + (f", skipped: {len(skipped)}" if skipped else "")
        + (f", failed: {', '.join(failed)}" if failed else "")
        + " ===\n"
    )
    emit(summary.strip())
    emit()

    logger.info(
        "Startup eval finished: %s/%s passed, %s skipped, %s failed",
        passed,
        len(cases),
        len(skipped),
        len(failed),
    )

    if report_file is not None:
        report_file.close()
        logger.info("Startup eval report written to %s", report_path_resolved)

    return not failed


def main() -> None:
    ok = run_startup_eval()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
