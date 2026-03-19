# ProjectEC

## 1. Project Overview
ProjectEC is a preventive medicine chatbot research project built with production-oriented engineering practices.

At a high level, the system combines:
- LLM generation (via Ollama)
- RAG over a vector store (Chroma) for literature-style explanations
- Tool-based reasoning backed by databases:
  - SQL (PostgreSQL) for structured statistics and drug/symptom mappings
  - MongoDB for WHO GHO indicators/dimensions and MedlinePlus disease summaries
- Observability (Langfuse + structured logging) for traceability and debugging

The goal is not only to answer questions, but also to make the behavior inspectable and extendable for future research iterations.

## 2. Features
- Chat interface: Streamlit UI + FastAPI backend (`/chat/`)
- Tool-based reasoning:
  - `rag_tool` (vector retrieval + reranking + LLM response)
  - `sql_tool` (safe SQL generation + execution + explanation)
  - `mongo_tool` (heuristic planning + Mongo context + LLM response)
- Observability:
  - Langfuse tracing spans per request and per tool
  - Application logging via a centralized logger

## 3. High-Level Architecture
- **FastAPI backend**: exposes the chat endpoint and orchestrates rules, tool selection, and tool execution.
- **Streamlit frontend**: provides a chat UI and calls the FastAPI endpoint.
- **Databases**:
  - PostgreSQL for structured health datasets used by the SQL tool
  - MongoDB for WHO GHO + MedlinePlus content used by the Mongo tool
  - Chroma for vector retrieval used by the RAG tool
- **Ollama**: runs the local LLM model used for generation and tool selection.
- **Langfuse**: receives traces/spans from the backend to visualize request flows.

## 4. Project Structure
This repository is organized into the following top-level directories:
- `apps/`: deployable application entrypoints (API + UI)
- `src/chat_saude/`: core chatbot implementation (services, tools, repositories, infrastructure, ingestion)
- `data/`: local datasets used for ingestion (CSVs/JSON/Excel, depending on the pipeline)
- `scripts/`: small manual CLI helpers for testing specific parts of the system
- `tests/`: automated tests

## 5. Setup Instructions
1. **Clone the repository**
   ```console
   git clone <repository-url>
   cd ProjetoEC
   ```
2. **Configure environment variables**
   ```console
   cp .env.example .env
   ```
3. **Start all services with Docker Compose**
   ```console
   docker-compose up --build
   ```

## 6. Services and URLs
Docker Compose exposes the following services (host:port):
- **UI (Streamlit)**: `http://localhost:8501`
- **API (FastAPI)**: `http://localhost:8500/chat/`
- **Langfuse**: `http://localhost:3000`
- **PostgreSQL (SQL tool backend)**: `localhost:5432`
- **MongoDB (Mongo tool backend)**: `localhost:27017`
- **Chroma (Vector store)**: `localhost:8002` (mapped from Chroma’s internal port)
- **Ollama (LLM runtime)**: `localhost:11434`
- **ClickHouse (used by Langfuse)**: `localhost:8123`, `localhost:9000`
- **MinIO (used by Langfuse)**: `localhost:9090`

If a database/service is not listed above, it is still used internally by containers, but not necessarily exposed to the host.

## 7. How to Use
1. Open the UI:
   - `http://localhost:8501`
2. Start a conversation by typing a medical/preventive question.
3. How tool selection works (briefly):
   - The backend first applies rules (validation, FAQ/domain filtering).
   - If no rule answers the request, an agent decides which tool(s) to use:
     - `rag_answer` for literature/explanation questions
     - `sql_query` for “numbers/statistics” questions
     - `mongo_query` for WHO GHO + MedlinePlus topic/dimension questions
     - One or more tools may be selected for a single question (e.g., RAG + SQL when both explanation and statistics are needed)

## 8. Development Notes
- **Ingestion is manual**: datasets and crawled content must be loaded by running the ingestion scripts/crawlers.
- **Designed for extensibility**:
  - Tool abstraction (`rag_tool`, `sql_query`, `mongo_query`) keeps the orchestration logic stable while enabling new tools.
  - Request orchestration is centralized in `ChatService`, making it easy to add new decision policies or tools.
  - The architecture is compatible with adding more agent/tool “endpoints” (e.g., MCP-style servers) as the research evolves.

