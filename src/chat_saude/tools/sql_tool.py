import os
import re
from urllib.parse import quote_plus

import yaml
from langchain_community.utilities import SQLDatabase
from langchain_ollama import ChatOllama

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
    """Lê um prompt específico do ficheiro YAML."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as file:
            prompts = yaml.safe_load(file)
            return prompts.get(key, "")
    except Exception as e:
        print(f"Erro ao ler {yaml_path}: {e}")
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
    Retorna um schema minimalista para economizar tokens.
    Formato: tabela (coluna1, coluna2, ...)
    """
    # Acessa o dicionário de tabelas do SQLAlchemy internamente
    metadata = db._metadata.tables
    slim_schema = []

    for table_name, table_obj in metadata.items():
        # Pega apenas os nomes das colunas, sem tipos ou constraints pesadas
        col_names = [col.name for col in table_obj.columns]
        slim_schema.append(f"{table_name} ({', '.join(col_names)})")
    print(f"Slim schema:\n{slim_schema}\n")  # Debug: mostrar schema minimalista
    return "\n".join(slim_schema)


def sql_query(user_question: str) -> str:
    """Generate and run a safe SQL query from a natural-language question."""

    db = SQLDatabase.from_uri(_build_postgres_uri())

    # 1. Obter apenas o essencial do schema
    schema = get_slim_schema(db)

    llm = ChatOllama(
        model=os.getenv("SQL_LLM_MODEL", "gemma3:4b"),
        base_url=os.getenv("OLLAMA_HOST", "http://ollama:11434"),
        temperature=0,
    )

    # Path to prompts: try repo layout (src/agents) then API Docker layout (/app/agents)
    _agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agents"))
    _prompts_candidates = [
        os.path.join(_agents_dir, "prompts.yaml"),
        "/app/agents/prompts.yaml",
    ]
    prompts_path = next((p for p in _prompts_candidates if os.path.isfile(p)), _prompts_candidates[0])
    gen_template = load_prompt(prompts_path, "sql_prompt")

    if not gen_template:
        return "Erro interno: Prompt de geração de SQL não encontrado."

    prompt_sql = gen_template.format(schema=schema, user_question=user_question)

    # 2. Gerar e extrair SQL
    raw_response = llm.invoke(prompt_sql)
    raw_sql = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
    generated_sql = _extract_sql(raw_sql)

    # 3. Validar SQL
    if not generated_sql or not _is_safe_query(generated_sql):
        return "Não consegui gerar uma query SQL segura (apenas SELECT é permitido)."

    print(f"Generated SQL:\n{generated_sql}\n")  # Debug: mostrar SQL gerada
    # 4. Executar SQL
    result = db.run_no_throw(generated_sql)

    if isinstance(result, str) and result.strip().startswith("Error"):
        return f"A query SQL falhou: {result}"

    if result in ("", "[]", [], None):
        return "Não encontrei resultados para essa pergunta na base de dados."

    # 5. Carregar prompt de explicação e gerar resposta final
    exp_template = load_prompt(prompts_path, "sql_explanation_prompt")

    if not exp_template:
        return f"Resultados brutos (Erro ao carregar prompt de explicação): {result}"

    explain_prompt = exp_template.format(
        user_question=user_question, generated_sql=generated_sql, result=result
    )

    final = llm.invoke(explain_prompt)
    return final.content if hasattr(final, "content") else str(final)
