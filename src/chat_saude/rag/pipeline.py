import os

import ollama
import yaml
from sentence_transformers import CrossEncoder, SentenceTransformer

from chat_saude.infrastructure.database.chroma import get_chroma_client

COLLECTION_NAME = "pmc_medicine_preventive"

embedding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
reranker = CrossEncoder("BAAI/bge-reranker-base")

chroma_client = get_chroma_client()
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

LLM_MODEL = "gemma3:4b"

# Path to prompts: try repo layout (src/agents) then API Docker layout (/app/agents)
_agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agents"))
_prompts_candidates = [
    os.path.join(_agents_dir, "prompts.yaml"),
    "/app/agents/prompts.yaml",
]
prompts_path = next((p for p in _prompts_candidates if os.path.isfile(p)), _prompts_candidates[0])


def rag_answer(query: str) -> str:
    # embedding
    emb = embedding_model.encode(query).tolist()

    # retrieval
    results = collection.query(query_embeddings=[emb], n_results=5)

    docs = results["documents"][0]

    # rerank
    pairs = [(query, d) for d in docs]
    scores = reranker.predict(pairs)

    ranked_docs = [d for _, d in sorted(zip(scores, docs), reverse=True)]

    contexto = "\n".join(ranked_docs[:3])

    with open(prompts_path, encoding="utf-8") as file:
        prompts = yaml.safe_load(file)
        rag_template = prompts.get("rag_prompt", "")

    if not rag_template:
        raise RuntimeError("RAG prompt template not found in prompts.yaml")

    prompt = rag_template.format(contexto=contexto, query=query)

    client = ollama.Client(host="http://ollama:11434")
    response = client.generate(model=LLM_MODEL, prompt=prompt)

    return response["response"]
