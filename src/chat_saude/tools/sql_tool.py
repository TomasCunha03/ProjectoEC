import concurrent.futures
import os
import re
from urllib.parse import quote_plus

import yaml
from langchain_community.utilities import SQLDatabase
from langchain_ollama import ChatOllama

from chat_saude.observability.langfuse_client import end_span, start_span
from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:1b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434").rstrip("/")

# Prevent unbounded generation (models can loop for a long time on degenerate SQL).
_SQL_GEN_NUM_PREDICT = 512
_SQL_EXPLAIN_NUM_PREDICT = 1024
_SQL_LLM_TIMEOUT_SEC = 120.0
_SQL_MAX_CHARS = 8000
# One initial generation plus at most one repair after EXPLAIN/DB error feedback.
_SQL_MAX_ATTEMPTS = 2

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


_STOPWORDS = frozenset(
    {
        "what",
        "when",
        "where",
        "which",
        "that",
        "this",
        "with",
        "from",
        "tell",
        "about",
        "have",
        "does",
        "did",
        "will",
        "your",
        "into",
        "than",
        "then",
        "them",
        "some",
        "many",
        "much",
        "been",
        "were",
        "being",
        "could",
        "would",
        "should",
        "there",
        "their",
        "please",
        "help",
        "know",
        "want",
        "need",
        "like",
        "make",
        "also",
        "just",
        "only",
        "very",
        "even",
    }
)


def _question_tokens(question: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", question.lower()) if w not in _STOPWORDS}


def _looks_like_medication_token(word: str) -> bool:
    """Heuristic for drug-like tokens not present in the YAML text (e.g. 'loratadine')."""
    if len(word) < 5:
        return False
    return bool(
        re.search(
            r"(?:tidine|tadine|cillin|mycin|zepam|azole|pril|olol|platin|stat|vir|done|fen|mab)$",
            word,
        )
    )


def build_focused_sql_data_context(user_question: str, yaml_path: str, max_tables: int = 14) -> str:
    """
    Build a smaller, relevance-ranked excerpt from sql_schema.yaml.

    Dumping the full YAML confuses small models (columns from one table get applied to another).
    """
    try:
        with open(yaml_path, encoding="utf-8") as f:
            parsed = yaml.safe_load(f) or {}
    except OSError as exc:
        logger.warning("Focused SQL context: read failed %s: %s — using raw file", yaml_path, exc)
        return load_sql_data_context(yaml_path)

    tables = parsed.get("tables")
    if not isinstance(tables, list):
        return load_sql_data_context(yaml_path)

    qlow = user_question.lower()
    toks = _question_tokens(user_question)

    scored: list[tuple[int, dict]] = []
    for t in tables:
        if not isinstance(t, dict):
            continue
        name = (t.get("name") or "").lower()
        desc = (t.get("description") or "").lower()
        col_names_lower: list[str] = []
        col_desc_text: list[str] = []
        for c in t.get("columns") or []:
            if isinstance(c, dict) and c.get("name"):
                col_names_lower.append(str(c["name"]).lower())
                cd = c.get("description")
                if isinstance(cd, str) and cd.strip():
                    col_desc_text.append(cd.lower())
        cf = t.get("common_filters") or []
        cf_txt = " ".join(str(x).lower() for x in cf if x) if isinstance(cf, list) else ""
        qp = t.get("query_patterns") or []
        qp_txt = " ".join(str(x).lower() for x in qp if x) if isinstance(qp, list) else ""
        blob = (
            f"{name} {desc} {' '.join(col_names_lower)} {' '.join(col_desc_text)} "
            f"{cf_txt} {qp_txt}"
        )

        score = sum(3 for w in toks if w and w in blob)
        score += sum(4 for w in toks if w and w in name.replace("_", " "))

        has_drug_columns = "drug_name" in col_names_lower or "generic_name" in col_names_lower
        if has_drug_columns and any(_looks_like_medication_token(w) for w in toks):
            score += 38

        # Soft topic routing (question wording + YAML table/column semantics)
        if re.search(
            r"\b(drugs?|medication|medicine|pill|tablet|prescription|dosage|rx|otc|"
            r"side\s+effects?|adverse|generic|brand)\b",
            qlow,
        ):
            if "drug" in name or name.endswith("_side_effects") or "side" in name:
                score += 28
        if re.search(r"\b(vaccine|immunization|coverage|wuenic|vaccination)\b", qlow):
            if "immunization" in name or "vaccine" in name or name in ("country_dim", "vaccine_dim"):
                score += 22
        if re.search(
            r"\b(prevalence|mortality|incidence|brfss|statistics|percentage|how\s+many|rate\s+in)\b",
            qlow,
        ):
            if any(
                x in name
                for x in ("brfss", "chronic_disease", "global_health", "indicator", "disease", "symptom")
            ):
                score += 15

        scored.append((score, t))

    scored.sort(key=lambda x: (-x[0], (x[1].get("name") or "")))

    lines: list[str] = []
    gr = parsed.get("global_rules")
    if isinstance(gr, list) and gr:
        lines.append("Global rules: " + "; ".join(str(x) for x in gr[:6]))
    summ = parsed.get("summary")
    if isinstance(summ, str) and summ.strip():
        lines.append(f"Summary: {summ.strip()}")
    lines.append("")
    lines.append(
        "Tables below are ordered by relevance to this question (highest first). "
        "Each column applies ONLY to that table."
    )
    lines.append("")

    for _, t in scored[:max_tables]:
        tname = t.get("name") or "unknown"
        desc = (t.get("description") or "").strip()
        col_objs = t.get("columns") or []
        col_names = [c["name"] for c in col_objs if isinstance(c, dict) and c.get("name")]
        lines.append(f"TABLE `{tname}` — {desc}")
        lines.append(f"  Columns (exact names): {', '.join(col_names)}")
        qpatterns = t.get("query_patterns") or []
        if isinstance(qpatterns, list) and qpatterns:
            lines.append(f"  Typical queries: {'; '.join(str(p) for p in qpatterns[:4])}")
        lines.append("")

    return "\n".join(lines).strip()


def _is_safe_query(query: str) -> bool:
    query_upper = query.upper().strip()

    if len(query) > _SQL_MAX_CHARS:
        return False

    if not query_upper.startswith("SELECT"):
        return False

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", query_upper):
            return False

    return True


def _is_sql_execution_error(output: object) -> bool:
    if output is None:
        return False
    s = output if isinstance(output, str) else str(output)
    s = s.strip()
    if not s:
        return False
    if s.startswith("Error"):
        return True
    if "psycopg2.errors" in s or "UndefinedColumn" in s or "does not exist" in s.lower():
        return True
    return False


def _repair_sql_query(
    llm_gen: ChatOllama,
    prompts_path: str,
    schema: str,
    data_context: str,
    user_question: str,
    failed_sql: str,
    error_message: str,
) -> str:
    tpl = load_prompt(prompts_path, "sql_repair_prompt")
    if not tpl:
        return ""
    prompt = tpl.format(
        error_message=error_message[:2500],
        failed_sql=failed_sql[:4000],
        schema=schema,
        data_context=data_context or "No extra table-content metadata available.",
        user_question=user_question,
    )
    try:
        return _invoke_ollama_chat(llm_gen, prompt)
    except TimeoutError:
        logger.warning("SQL repair LLM call exceeded %.1fs", _SQL_LLM_TIMEOUT_SEC)
        return ""


_SQL_PLACEHOLDER_HINT = (
    "The SQL contains forbidden placeholder identifiers such as table_name or column_name. "
    "Those tokens are NOT real PostgreSQL tables or columns. Rewrite using ONLY names that "
    "appear verbatim in LIVE SCHEMA."
)

_PLACEHOLDER_SQL_ID_RE = re.compile(
    r"\b(?:"
    r"table_name|column_name|schema_name|database_name|"
    r"your_table|your_column|some_table|some_column|"
    r"example_table|example_column|tbl_name|col_name"
    r")\b",
    re.IGNORECASE,
)


def _has_sql_placeholders(sql: str) -> bool:
    if not sql:
        return False
    return _PLACEHOLDER_SQL_ID_RE.search(sql) is not None


def _apply_placeholder_repairs(
    llm_gen: ChatOllama,
    prompts_path: str,
    schema: str,
    data_context: str,
    user_question: str,
    sql_in: str,
    *,
    max_rounds: int = 2,
) -> tuple[str | None, str]:
    """Rewrite tutorial-style identifiers; returns (fixed_sql or None, last_attempt)."""
    sql_work = sql_in
    for round_i in range(max_rounds):
        if not _has_sql_placeholders(sql_work):
            return sql_work, sql_work
        logger.warning(
            "SQL placeholder identifiers detected (round %s): %s",
            round_i + 1,
            sql_work[:400],
        )
        raw_fix = _repair_sql_query(
            llm_gen,
            prompts_path,
            schema,
            data_context or "",
            user_question,
            sql_work,
            _SQL_PLACEHOLDER_HINT,
        )
        sql_work = _extract_sql(raw_fix)
        if (
            _is_degenerate_sql_extracted(sql_work)
            or not sql_work
            or not _is_safe_query(sql_work)
        ):
            return None, sql_work
    if _has_sql_placeholders(sql_work):
        return None, sql_work
    return sql_work, sql_work


def _is_degenerate_sql_extracted(sql: str) -> bool:
    """Detect repetitive LLM garbage (e.g. CASE WHEN loops) before safety checks."""
    if not sql:
        return False
    if len(sql) > _SQL_MAX_CHARS:
        logger.warning("SQL rejected: length %s exceeds cap %s", len(sql), _SQL_MAX_CHARS)
        return True
    upper = sql.upper()
    if upper.count("CASE WHEN") > 25:
        return True
    if re.search(r"(CASE\s+WHEN\s*){15,}", sql, flags=re.IGNORECASE):
        return True
    return False


def _invoke_ollama_chat(llm: ChatOllama, prompt: str) -> str:
    """Run ChatOllama.invoke with a hard timeout (invoke itself has no deadline)."""

    def _run() -> str:
        raw = llm.invoke(prompt)
        return raw.content if hasattr(raw, "content") else str(raw)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_run)
    try:
        return future.result(timeout=_SQL_LLM_TIMEOUT_SEC)
    finally:
        executor.shutdown(wait=False)


def _extract_sql(raw_output: str) -> str:
    text = raw_output.strip()
    text = re.sub(r"^\s*sql\s+", "", text, count=1, flags=re.IGNORECASE)

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
    Return a minimal schema for the LLM with explicit table ↔ column binding.
    """
    metadata = db._metadata.tables
    blocks: list[str] = []

    for table_name, table_obj in sorted(metadata.items()):
        col_names = [col.name for col in table_obj.columns]
        blocks.append(f'TABLE "{table_name}"')
        blocks.append(f"  Columns: {', '.join(col_names)}")
        blocks.append("")

    logger.info("Slim schema tables: %s", list(sorted(metadata.keys())))
    return "\n".join(blocks).strip()


def sql_query(user_question: str) -> str:
    """Generate and run a safe SQL query from a natural-language question."""
    logger.info("SQL tool input: %s", user_question)
    span = start_span(name="sql_tool", input_payload={"question": user_question})

    try:
        db = SQLDatabase.from_uri(_build_postgres_uri())

        # 1. Obter apenas o essencial do schema
        schema = get_slim_schema(db)

        llm_gen = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_HOST,
            temperature=0,
            num_predict=_SQL_GEN_NUM_PREDICT,
        )
        llm_explain = ChatOllama(
            model=LLM_MODEL,
            base_url=OLLAMA_HOST,
            temperature=0,
            num_predict=_SQL_EXPLAIN_NUM_PREDICT,
        )

        base_dir = os.path.dirname(__file__)
        prompts_path = os.path.abspath(os.path.join(base_dir, "..", "..", "agents", "prompts.yaml"))
        data_context_path = os.path.abspath(
            os.path.join(base_dir, "..", "..", "agents", "sql_schema.yaml")
        )
        gen_template = load_prompt(prompts_path, "sql_prompt")
        data_context = build_focused_sql_data_context(user_question, data_context_path)

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

        # 2. Gerar e extrair SQL (bounded tokens + wall-clock timeout)
        try:
            raw_sql = _invoke_ollama_chat(llm_gen, prompt_sql)
        except TimeoutError:
            msg = (
                "Database statistics lookup timed out. Try a question that clearly asks for numbers, "
                "rates, or comparisons (for example prevalence in a country)."
            )
            logger.warning("SQL generation LLM call exceeded %.1fs", _SQL_LLM_TIMEOUT_SEC)
            end_span(
                span,
                output_payload={"error": msg},
                level="ERROR",
                status_message="sql_llm_timeout",
            )
            return msg

        if len(raw_sql) > _SQL_MAX_CHARS * 2:
            msg = "Could not generate a valid SQL query for this question."
            end_span(
                span,
                output_payload={"error": msg, "raw_len": len(raw_sql)},
                level="ERROR",
                status_message="sql_raw_oversized",
            )
            return msg

        generated_sql = _extract_sql(raw_sql)
        _prev = generated_sql[:500] + ("..." if len(generated_sql) > 500 else "")
        logger.info("Generated SQL query: %s", _prev)

        # 3. Validar SQL
        if _is_degenerate_sql_extracted(generated_sql):
            msg = "Could not generate a safe SQL query (only SELECT is allowed)."
            end_span(
                span,
                output_payload={
                    "generated_sql": generated_sql[:2000],
                    "error": msg,
                },
                level="ERROR",
                status_message="degenerate_sql",
            )
            return msg

        if not generated_sql or not _is_safe_query(generated_sql):
            msg = "Could not generate a safe SQL query (only SELECT is allowed)."
            end_span(
                span,
                output_payload={"generated_sql": generated_sql[:2000], "error": msg},
                level="ERROR",
                status_message="unsafe_sql",
            )
            return msg

        fixed_sql, last_placeholder_attempt = _apply_placeholder_repairs(
            llm_gen,
            prompts_path,
            schema,
            data_context or "",
            user_question,
            generated_sql,
            max_rounds=3,
        )
        if fixed_sql is None:
            msg = (
                "Could not generate SQL using real table and column names from the database schema."
            )
            end_span(
                span,
                output_payload={
                    "generated_sql": last_placeholder_attempt[:2000],
                    "error": msg,
                    "placeholder_cleanup_failed": True,
                },
                level="ERROR",
                status_message="sql_placeholder",
            )
            return msg
        generated_sql = fixed_sql

        # 4. EXPLAIN + execute with one repair round on PostgreSQL errors (undefined column, etc.)
        sql_work = generated_sql
        result: object | None = None
        for attempt in range(_SQL_MAX_ATTEMPTS):
            explain_out = db.run_no_throw(f"EXPLAIN {sql_work}")
            if _is_sql_execution_error(explain_out):
                last_error = explain_out if isinstance(explain_out, str) else str(explain_out)
                logger.warning(
                    "SQL EXPLAIN failed (attempt %s): %s", attempt + 1, last_error[:500]
                )
                if attempt + 1 >= _SQL_MAX_ATTEMPTS:
                    msg = f"SQL query failed: {last_error}"
                    end_span(
                        span,
                        output_payload={
                            "generated_sql": sql_work,
                            "error": msg,
                            "repair_attempted": attempt > 0,
                        },
                        level="ERROR",
                        status_message="sql_explain_error",
                    )
                    return msg
                raw_fix = _repair_sql_query(
                    llm_gen,
                    prompts_path,
                    schema,
                    data_context or "",
                    user_question,
                    sql_work,
                    last_error,
                )
                sql_work = _extract_sql(raw_fix)
                if (
                    _is_degenerate_sql_extracted(sql_work)
                    or not sql_work
                    or not _is_safe_query(sql_work)
                ):
                    msg = f"SQL query failed: {last_error}"
                    end_span(
                        span,
                        output_payload={
                            "generated_sql": generated_sql,
                            "error": msg,
                            "repair_failed": True,
                        },
                        level="ERROR",
                        status_message="sql_repair_invalid",
                    )
                    return msg
                scrubbed, scrub_last = _apply_placeholder_repairs(
                    llm_gen,
                    prompts_path,
                    schema,
                    data_context or "",
                    user_question,
                    sql_work,
                    max_rounds=2,
                )
                if scrubbed is None:
                    msg = (
                        "Could not generate SQL using real table and column names from the "
                        "database schema."
                    )
                    end_span(
                        span,
                        output_payload={
                            "generated_sql": scrub_last[:2000],
                            "error": msg,
                            "placeholder_cleanup_failed": True,
                        },
                        level="ERROR",
                        status_message="sql_placeholder_after_repair",
                    )
                    return msg
                sql_work = scrubbed
                generated_sql = sql_work
                continue

            result = db.run_no_throw(sql_work)

            if _is_sql_execution_error(result):
                last_err = result if isinstance(result, str) else str(result)
                logger.warning(
                    "SQL execution failed (attempt %s): %s", attempt + 1, last_err[:500]
                )
                if attempt + 1 >= _SQL_MAX_ATTEMPTS:
                    msg = f"SQL query failed: {last_err}"
                    end_span(
                        span,
                        output_payload={
                            "generated_sql": sql_work,
                            "error": msg,
                            "repair_attempted": attempt > 0,
                        },
                        level="ERROR",
                        status_message="sql_execution_error",
                    )
                    return msg
                raw_fix = _repair_sql_query(
                    llm_gen,
                    prompts_path,
                    schema,
                    data_context or "",
                    user_question,
                    sql_work,
                    last_err,
                )
                sql_work = _extract_sql(raw_fix)
                if (
                    _is_degenerate_sql_extracted(sql_work)
                    or not sql_work
                    or not _is_safe_query(sql_work)
                ):
                    msg = f"SQL query failed: {last_err}"
                    end_span(
                        span,
                        output_payload={
                            "generated_sql": generated_sql,
                            "error": msg,
                            "repair_failed": True,
                        },
                        level="ERROR",
                        status_message="sql_repair_invalid",
                    )
                    return msg
                scrubbed, scrub_last = _apply_placeholder_repairs(
                    llm_gen,
                    prompts_path,
                    schema,
                    data_context or "",
                    user_question,
                    sql_work,
                    max_rounds=2,
                )
                if scrubbed is None:
                    msg = (
                        "Could not generate SQL using real table and column names from the "
                        "database schema."
                    )
                    end_span(
                        span,
                        output_payload={
                            "generated_sql": scrub_last[:2000],
                            "error": msg,
                            "placeholder_cleanup_failed": True,
                        },
                        level="ERROR",
                        status_message="sql_placeholder_after_repair",
                    )
                    return msg
                sql_work = scrubbed
                generated_sql = sql_work
                continue

            generated_sql = sql_work
            break

        if result is None:
            msg = "Could not run the SQL query for this question."
            end_span(
                span,
                output_payload={"generated_sql": generated_sql, "error": msg},
                level="ERROR",
                status_message="sql_no_result",
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

        try:
            final_text = _invoke_ollama_chat(llm_explain, explain_prompt)
        except TimeoutError:
            msg = (
                f"Query returned: {result}\n\n"
                "(Explanation step timed out; partial database result above.)"
            )
            end_span(
                span,
                output_payload={
                    "generated_sql": generated_sql,
                    "result": result,
                    "final_text": msg,
                },
                level="ERROR",
                status_message="sql_explain_timeout",
            )
            return msg
        end_span(
            span,
            output_payload={
                "generated_sql": generated_sql,
                "db_result_raw": result,
                "result_row_estimate": len(str(result)),
                "final_text": final_text,
                "schema_digest": {"lines": len(schema.splitlines()), "chars": len(schema)},
                "prompt_sizes": {
                    "sql_generation_chars": len(prompt_sql),
                    "explanation_chars": len(explain_prompt),
                },
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
