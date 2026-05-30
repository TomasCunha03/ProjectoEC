# Tests

## Scope
These are unit tests focused on core logic. No external services are called.
Heavy dependencies (LLMs, databases, vector stores) are stubbed so the suite stays fast and offline.

## How to run
- From the repo root, run: pytest
- To run a single file: pytest tests/test_dashboard_tool.py
- To run a single test: pytest tests/test_dashboard_tool.py -k test_dashboard_tool_reset_short_circuits

## Test map
- test_1.py: Minimal sanity test (kept intentionally trivial).
- test_logger.py: Logger helper behavior.
- test_chat_service_core.py: ChatService orchestration and resilience behavior (tool selection, fallbacks).
- test_sql_helpers.py: SQL helper parsing and safety checks with stubbed deps.
- test_mongo_helpers.py: Mongo context construction helpers with stubbed accessors.
- test_rag_tool.py: RAG tool wrapper behavior and span recording with stubs.
- test_langfuse_client.py: Langfuse client helpers and noop behavior.
- test_dashboard_tool.py: Dashboard filter extraction and coercion with stubbed LLM.
- test_rules.py: Rule engine checks (emergency, FAQ, domain) with stubs.

## Conventions
- tests/conftest.py adds src and apps to sys.path for imports.
- Stubs are injected via sys.modules to avoid importing heavy libraries.
- Do not test real tool execution here; keep those as separate integration tests.

## Adding new tests
- Prefer small helpers that accept stub functions instead of patching deep internals.
- If a module is not a package (no __init__.py), load by file path using importlib.util.
- Keep tests deterministic; avoid time-based or random assertions.
