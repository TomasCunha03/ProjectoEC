# Architecture

## 1. System Architecture (containers)
The project is deployed with `docker-compose.yml`. Containers collaborate as follows:

```
                +-------------------+
                |   Langfuse (3000) |
                +---------+---------+
                          ^
                          | traces/spans
                          |
+-------------------------+-------------------------+
|                    Backend (API)                 |
|        FastAPI (8500) + ChatService orchestration |
|                                                     |
+--------------------------+--------------------------+
                           |
                           | HTTP (/chat/)
                           v
+--------------------------+--------------------------+
|                    Frontend (UI)                   |
|                 Streamlit (8501)                 |
+--------------------------+--------------------------+
                           |
                           | Ollama (11434)
                           v
                     +-----+-----+
                     | Ollama     |
                     +-----------+

Chat tools access databases/vector store:
  - SQL tool -> PostgreSQL
  - Mongo tool -> MongoDB
  - RAG tool  -> Chroma (vector store)

Langfuse internal dependencies:
  - langfuse-db (Postgres)
  - clickhouse
  - redis
  - minio
```

### docker-compose services (high level)
- `app`: Streamlit UI container (exposes `APP_PORT`, default `8501`)
- `api`: FastAPI container (exposes `8500`)
- `ollama`: LLM runtime container (exposes `11434`)
- `db_sql`: PostgreSQL container (exposes `SQL_PORT`, default `5432`)
- `db_nosql`: MongoDB container (exposes `MONGO_PORT`, default `27017`)
- `db_vector`: ChromaDB container (exposes `VECTOR_PORT` on host; Chroma listens on `8000` internally)
- `langfuse`: Langfuse web app (exposes `3000`)
- `langfuse-db`, `langfuse-worker`, `clickhouse`, `redis`, `minio`: Langfuse dependencies (some exposed for debugging)

## 2. Application Architecture
The codebase follows a layered approach so orchestration remains stable while implementations evolve.

- `apps/`
  - Application entrypoints (Streamlit UI and FastAPI API routing)
- `src/chat_saude/services/`
  - Request orchestration (`ChatService`): rules -> tool selection -> tool execution -> trace finalization
- `src/chat_saude/tools/`
  - Tool implementations called by `ChatService`:
    - `rag_tool` (RAG pipeline)
    - `sql_query` (safe SQL generation/execution + explanation)
    - `mongo_query` (heuristic planning + Mongo context + LLM response)
- `src/chat_saude/repositories/`
  - Data access abstractions over specific backends (Postgres/Mongo/Chroma)
- `src/chat_saude/infrastructure/`
  - Low-level infrastructure helpers (DB clients, connection factories, health checks)

There are also focused submodules under `src/chat_saude/`:
- `rag/`: retrieval + reranking pipeline for RAG
- `ingestion/`: ETL/crawlers/API ingesters that populate Postgres, MongoDB, and Chroma
- `observability/`: Langfuse span/tracing helpers + logging

## 3. Chat Flow
This section describes what happens for one user message from the UI to the final response.

1. **User sends a message in the Streamlit UI**
   - Streamlit posts JSON `{ "message": <user text> }` to the backend endpoint.
2. **FastAPI receives the request**
   - Endpoint: `POST /chat/`
   - It calls `ChatService.handle_chat(message)`.
3. **`ChatService` starts observability tracing**
   - A Langfuse root trace is created for the request.
4. **Rules are applied first**
   - Validation (non-empty/length constraints)
   - FAQ matching
   - Domain filtering (medical vs non-medical) using sentence embeddings
   - If rules produce an answer, `ChatService` returns immediately.
5. **Tool selection**
   - An agent-based decision chooses one of: `rag_answer`, `sql_query`, `mongo_query`, or `both`.
   - The agent uses Ollama with a `system_prompt` that instructs it to output a single decision keyword.
6. **Tool execution**
   - `rag_answer`: vector retrieval (Chroma) + reranking + LLM response
   - `sql_query`:
    - Build a "slim" schema description
     - Ask Ollama to generate SQL (SELECT-only)
     - Validate/parse the SQL text
     - Execute against Postgres
     - Ask Ollama to explain results
   - `mongo_query`:
    - Determine a query "plan" with regex/heuristics
     - Fetch relevant Mongo context (WHO + MedlinePlus collections)
     - Ask Ollama to answer using the retrieved context
   - `both` runs RAG and SQL and concatenates the responses.
7. **`ChatService` finalizes tracing**
   - The final output is attached to the Langfuse trace and spans are ended.
8. **FastAPI returns `{ "response": <text>, "tool_used": <tool> }`**
9. **Streamlit renders the assistant response**

## 4. Tools Architecture
### RAG tool (`rag_tool`)
Responsibilities:
- Convert the user query into embeddings
- Retrieve candidate documents from Chroma
- Rerank retrieved chunks with a cross-encoder
- Build the final prompt from `rag_prompt` and generate the answer using Ollama

Key components:
- Vector retrieval and reranking in `src/chat_saude/rag/pipeline.py`
- Prompt templates from `src/agents/prompts.yaml`

### SQL tool (`sql_query`)
Responsibilities:
- Convert a natural-language question into a safe SQL query
- Execute it against PostgreSQL
- Generate a final explanation grounded in both the query and results

Safety constraints (as implemented):
- Only `SELECT` is allowed.
- Forbidden SQL keywords (e.g. `INSERT`, `DROP`, etc.) are rejected.
- SQL is extracted from model output (supports fenced ` ```sql ... ``` ` blocks).

### Mongo tool (`mongo_query`)
Responsibilities:
- Plan the MongoDB query type using regex/heuristic detection (no LLM required for planning)
- Fetch relevant context from MongoDB collections
- Use Ollama to generate a user-facing response based on that context

Mongo "actions" map to different context builders (e.g. indicator search, dimension values, MedlinePlus topic lookup).

## 5. Data Layer
The chatbot uses multiple databases so each tool can use the most appropriate storage/access pattern.

### PostgreSQL (SQL tool)
Postgres stores structured, queryable datasets and supports analytics-style questions:
- Disease/symptom model:
  - `diseases`, `symptoms`, `disease_symptoms`, `disease_precautions`
- Global health statistics:
  - `global_health_stats`
- Chronic disease indicators:
  - `chronic_disease_indicators`
- BRFSS survey responses:
  - `brfss_responses`
- Vaccination/coverage (WUENIC):
  - `country_dim`, `vaccine_dim`, `immunization_fact`
- Drugs side effects:
  - `drugs_side_effects`

### MongoDB (Mongo tool)
MongoDB stores semi-structured WHO/health-topic information:
- WHO GHO:
  - `gho_indicators`
  - `gho_dimensions`
  - one collection per dimension values set, e.g. `gho_<dimension>_dimension_values`
- MedlinePlus:
  - `medlineplus_health_topics`

### Chroma (RAG tool)
Chroma stores embedded text chunks used for retrieval:
- Collection used by the RAG pipeline:
  - `pmc_medicine_preventive`
- Retrieval flow:
  - embed query -> `collection.query(...)`
  - rerank returned chunks -> create `context`

## 6. Observability
### Langfuse tracing
The backend creates manual Langfuse spans:
- `start_trace(...)` creates a root span for the request
- `start_span(...)` creates nested spans (rules, tool_selection, rag/sql/mongo)
- `end_span(...)` updates and ends each span with outputs/errors when applicable
- `finalize_trace(...)` updates the root trace with the final response payload

If Langfuse credentials are not present in the environment, the client becomes a no-op (so the app still runs locally).

### Logging
The `logger.py` module sets a consistent root logging configuration and provides `get_logger(name)` for per-module loggers.

## 7. Ingestion
Ingestion is manual and designed to populate the three tool backends (Postgres, MongoDB, Chroma).

### Postgres ingestion (ETL)
ETL entrypoints live in `src/chat_saude/ingestion/etl/` and load datasets into the SQL schema.
Examples:
- `ingest_global_stats(csv_path)` -> `global_health_stats`
- `ingest_drugs(csv_path)` -> `drugs_side_effects`
- `ingest_brfss(csv_path)` -> `brfss_responses`
- `ingest_cdi(csv_path)` -> `chronic_disease_indicators`
- `ingest_wuenic(filepath)` -> vaccination coverage tables

### Mongo ingestion (APIs)
API ingestion entrypoints live in `src/chat_saude/ingestion/api/`:
- `gho.py`: fetches WHO GHO indicators/dimensions/dimension values into MongoDB
- `medlineplus.py`: fetches MedlinePlus summaries for diseases found in Postgres (or derived as fallback)

These scripts require outbound network access to the upstream APIs.

### Chroma ingestion (crawlers/vector build)
Vector ingestion is performed via crawlers and scripts that:
- collect text sources (JSON/PDF/HTML depending on the crawler)
- chunk documents
- embed chunks
- write embeddings into Chroma collection(s)

Example script:
- `src/chat_saude/ingestion/crawlers/chromadb_ingest.py` loads JSON from `data/` and stores chunked embeddings into the `pmc_medicine_preventive` collection.

### Running ingestion (examples)
From the repository root:

1. Start containers (so DB endpoints are reachable):
   ```console
   docker-compose up --build
   ```
2. Ingest WUENIC (example already used by the project):
   ```bash
   PYTHONPATH=src python -c "from chat_saude.ingestion.etl.ingest_wuenic import ingest_wuenic; ingest_wuenic('data/wuenic-input.xlsx')"
   ```
3. Test tools interactively:
   - RAG:
     ```console
     PYTHONPATH=src python scripts/rag_cli.py
     ```
   - Mongo tool:
     ```console
     PYTHONPATH=src python scripts/mongo_tool_terminal.py
     ```

