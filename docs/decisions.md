# Architecture Decisions

## Why `ChatService`
`ChatService` is the single orchestration point for the whole request lifecycle:
- It applies rule-based short-circuiting (validation/FAQ/domain checks).
- It delegates tool selection to a dedicated agent (`select_tool`) instead of hard-coding logic in the UI/API layer.
- It calls the appropriate tool(s) and normalizes the response payload (`{ "response": ..., "tool_used": ... }`).
- It owns the Langfuse tracing lifecycle (start root trace, nested spans per step/tool, and finalization).

This design keeps the FastAPI endpoint thin and makes the behavior consistent across different frontends (current Streamlit UI, future clients, etc.).

## Why tools abstraction (`rag_tool`, `sql_query`, `mongo_query`)
Each tool encapsulates:
- its own "input contract" (user question -> tool output text),
- its own data access strategy (Chroma vs Postgres vs Mongo),
- and its own generation constraints.

In particular, the SQL tool includes safety measures (SELECT-only filtering, forbidden keyword rejection, and extraction of generated SQL from the model output). By isolating that logic in `sql_query`, you reduce the chance of unsafe SQL leaking into the rest of the system.

This separation also makes it easy to add new tools later without redesigning request orchestration.

## Why multiple databases
The project uses different databases because the question types and retrieval needs differ:
- **PostgreSQL** is ideal for structured analytics-style answers (rates/counts, year/country/age slices) and for normalized entities like `diseases`/`symptoms`.
- **MongoDB** is well suited for GHO indicator metadata and variable-shaped collections (dimensions, dimension values, and topic summaries).
- **Chroma** provides vector search for literature-style context, enabling RAG with retrieval + reranking.

By mapping each tool to the data store that best matches its problem, the chatbot can be both more accurate and more extensible.

## Why Langfuse
This is a research project where understanding model/tool behavior matters as much as the final text.

Langfuse provides:
- a request-level trace for the full pipeline,
- step-level spans (rules, tool selection, and each tool execution),
- and output/error recording per span.

That makes it possible to debug failures, compare tool routing quality, and measure how often each backend contributes to the final response.

