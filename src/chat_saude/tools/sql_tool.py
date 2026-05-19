import os
import re
from urllib.parse import quote_plus

import torch
import yaml
from langchain_community.utilities import SQLDatabase
from langchain_ollama import ChatOllama
from sentence_transformers import SentenceTransformer, util

from chat_saude.observability.langfuse_client import end_span, start_span
from chat_saude.observability.logger import get_logger

embedding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")

logger = get_logger(__name__)

FORBIDDEN_KEYWORDS = [
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
]


def get_relevant_schema(user_question: str, yaml_path: str, top_k: int = 3) -> str:
    """
    Retrieve only the most relevant table schemas for the user question.
    """

    with open(yaml_path, "r", encoding="utf-8") as file:
        schema_data = yaml.safe_load(file)

    tables = schema_data.get("tables", [])

    table_chunks = []

    for table in tables:
        table_name = table.get("name", "")
        description = table.get("description", "")

        columns = []
        for col in table.get("columns", []):
            columns.append(f"{col.get('name')} ({col.get('type')}): {col.get('description', '')}")

        query_patterns = table.get("query_patterns", [])

        chunk = f"""
        Table: {table_name}

        Description:
        {description}

        Columns:
        {"; ".join(columns)}

        Query patterns:
        {"; ".join(query_patterns)}
        """

        table_chunks.append(chunk)

    chunk_embeddings = embedding_model.encode(table_chunks, convert_to_tensor=True)

    query_embedding = embedding_model.encode(user_question, convert_to_tensor=True)

    scores = util.cos_sim(query_embedding, chunk_embeddings)[0]

    top_results = torch.topk(scores, k=min(top_k, len(table_chunks)))

    selected_chunks = []

    for idx in top_results.indices:
        selected_chunks.append(table_chunks[idx])

    return "\n\n".join(selected_chunks)


def load_prompt(yaml_path: str, key: str) -> str:
    """Load a specific prompt from a YAML file."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as file:
            prompts = yaml.safe_load(file)
            return prompts.get(key, "")
    except Exception as e:
        logger.warning("Error reading %s: %s", yaml_path, e)
        return ""


def load_sql_data_context(yaml_path: str) -> str:
    """Load SQL data context as raw YAML text for direct prompt injection."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        logger.warning("SQL data context file not found: %s", yaml_path)
        return ""
    except Exception as exc:
        logger.warning("Failed to read SQL data context file %s: %s", yaml_path, exc)
        return ""


def _is_safe_query(query: str) -> bool:
    query_upper = query.upper().strip()

    if not query_upper.startswith("SELECT"):
        return False

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", query_upper):
            return False

    return True


def _extract_sql(raw_output: str) -> str:
    text = raw_output.strip()

    code_block = re.search(r"```sql\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if code_block:
        return code_block.group(1).strip()

    labelled = re.search(r"SQLQuery\s*:\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
    if labelled:
        text = labelled.group(1).strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    candidate = " ".join(lines)
    candidate = candidate.rstrip(";")
    return candidate


def _build_postgres_uri() -> str:
    host = os.getenv("SQL_HOST", "localhost")
    port = os.getenv("SQL_PORT", "5432")
    database = os.getenv("SQL_DB", "")
    user = quote_plus(os.getenv("SQL_USER", ""))
    password = quote_plus(os.getenv("SQL_PASSWORD", ""))

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def get_slim_schema(db):
    """
    Return a minimal schema description to save tokens.
    Format: table (column1, column2, ...)
    """
    # Access SQLAlchemy's internal table metadata
    metadata = db._metadata.tables
    slim_schema = []

    for table_name, table_obj in metadata.items():
        # Only include column names (no heavy types/constraints)
        col_names = [col.name for col in table_obj.columns]
        slim_schema.append(f"{table_name} ({', '.join(col_names)})")
    logger.info("Slim schema: %s", slim_schema)
    return "\n".join(slim_schema)


def sql_query(user_question: str) -> str:
    """Generate and run a safe SQL query from a natural-language question."""
    logger.info("SQL tool input: %s", user_question)
    span = start_span(name="sql_tool", input_payload={"question": user_question})

    try:
        db = SQLDatabase.from_uri(_build_postgres_uri())

        # 1. Obter apenas o essencial do schema
        schema = get_slim_schema(db)

        llm = ChatOllama(
            model=os.getenv("SQL_LLM_MODEL", "gemma3:1b"),
            base_url=os.getenv("OLLAMA_HOST", "http://ollama:11434"),
            temperature=0,
        )

        base_dir = os.path.dirname(__file__)
        prompts_path = os.path.abspath(os.path.join(base_dir, "..", "..", "agents", "prompts.yaml"))
        data_context_path = os.path.abspath(
            os.path.join(base_dir, "..", "..", "agents", "sql_schema.yaml")
        )
        gen_template = load_prompt(prompts_path, "sql_prompt")
        data_context = get_relevant_schema(
            user_question=user_question, yaml_path=data_context_path, top_k=3
        )

        if not gen_template:
            msg = "Internal error: SQL generation prompt not found."
            end_span(
                span, output_payload={"error": msg}, level="ERROR", status_message="prompt_missing"
            )
            return msg

        prompt_sql = gen_template.format(
            schema=schema,
            data_context=data_context or "No extra table-content metadata available.",
            user_question=user_question,
        )

        # 2. Gerar e extrair SQL
        raw_response = llm.invoke(prompt_sql)
        raw_sql = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
        generated_sql = _extract_sql(raw_sql)
        logger.info("Generated SQL query: %s", generated_sql)

        # 3. Validar SQL
        if not generated_sql or not _is_safe_query(generated_sql):
            msg = "Could not generate a safe SQL query (only SELECT is allowed)."
            end_span(
                span,
                output_payload={"generated_sql": generated_sql, "error": msg},
                level="ERROR",
                status_message="unsafe_sql",
            )
            return msg

        # 4. Executar SQL
        result = db.run_no_throw(generated_sql)

        if isinstance(result, str) and result.strip().startswith("Error"):
            msg = f"SQL query failed: {result}"
            end_span(
                span,
                output_payload={"generated_sql": generated_sql, "error": msg},
                level="ERROR",
                status_message="sql_execution_error",
            )
            return msg

        if result in ("", "[]", [], None):
            msg = "No results found for this question in the database."
            end_span(span, output_payload={"generated_sql": generated_sql, "result": result})
            return msg

        # 5. Load explanation prompt and generate the final response
        exp_template = load_prompt(prompts_path, "sql_explanation_prompt")

        if not exp_template:
            msg = f"Raw results (error loading explanation prompt): {result}"
            end_span(span, output_payload={"generated_sql": generated_sql, "result": result})
            return msg

        explain_prompt = exp_template.format(
            user_question=user_question, generated_sql=generated_sql, result=result
        )

        final = llm.invoke(explain_prompt)
        final_text = final.content if hasattr(final, "content") else str(final)
        end_span(
            span,
            output_payload={
                "generated_sql": generated_sql,
                "result": result,
                "final_text": final_text,
            },
        )
        return final_text
    except Exception as exc:
        logger.exception("SQL tool failed")
        end_span(
            span,
            output_payload={"error": str(exc)},
            level="ERROR",
            status_message="sql_tool_error",
        )
        raise
