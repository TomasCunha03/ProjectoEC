import os

import ollama
import yaml

LLM_MODEL = "gemma3:4b"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

def load_prompt(file_path="prompts.yaml", key="system_prompt") -> str:
    """Lê o ficheiro YAML e extrai o prompt correspondente."""

    if not os.path.isabs(file_path):
        file_path = os.path.join(os.path.dirname(__file__), file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            prompts = yaml.safe_load(file)
            return prompts.get(key, "")
    except FileNotFoundError:
        print(f"Erro: Ficheiro {file_path} não encontrado!")
        return ""
    except Exception as e:
        print(f"Erro ao ler YAML: {e}")
        return ""

def select_tool(user_question: str) -> dict:
    """Select appropriate tool based on user question."""
    system_prompt = load_prompt("prompts.yaml", "system_prompt")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    client = ollama.Client(host=OLLAMA_HOST)
    response = client.chat(model=LLM_MODEL, messages=messages)
    answer = response["message"]["content"].strip().upper()

    # Parse response
    if "BOTH" in answer:
        return {"tool": "both", "query": user_question}
    elif "RAG" in answer:
        return {"tool": "rag_answer", "query": user_question}
    elif "SQL" in answer:
        return {"tool": "sql_query", "query": user_question}
    elif "MONGO" in answer:
        return {"tool": "mongo_query", "query": user_question}
    else:
        return {"tool": None, "query": user_question}