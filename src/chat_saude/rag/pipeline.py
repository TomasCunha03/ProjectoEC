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

# Load rag_prompt from prompts.yaml (src/chat_saude/rag: .. -> chat_saude, .. -> src, agents)
agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agents"))
prompts_path = os.path.join(agents_dir, "prompts.yaml")
rag_corpus_path = os.path.join(agents_dir, "rag_corpus.yaml")


def _load_rag_corpus_text() -> str:
    try:
        with open(rag_corpus_path, encoding="utf-8") as file:
            corpus = yaml.safe_load(file) or {}
    except FileNotFoundError:
        return ""
    except Exception:
        return ""

    lines = []
    summary = corpus.get("summary")
    if summary:
        lines.append(f"RAG corpus summary: {summary}")

    corpus_info = corpus.get("corpus", {})
    collection_name = corpus_info.get("collection_name")
    domain = corpus_info.get("domain")
    document_type = corpus_info.get("document_type")
    strengths = corpus_info.get("strengths", [])
    limitations = corpus_info.get("limitations", [])
    metadata_fields = corpus_info.get("metadata_fields", [])

    if collection_name or domain or document_type:
        lines.append("RAG corpus details:")
        if collection_name:
            lines.append(f"  - Collection: {collection_name}")
        if domain:
            lines.append(f"  - Domain: {domain}")
        if document_type:
            lines.append(f"  - Document type: {document_type}")
    if metadata_fields:
        lines.append(f"  - Metadata fields: {', '.join(metadata_fields)}")
    if strengths:
        lines.append(f"  - Strengths: {'; '.join(strengths)}")
    if limitations:
        lines.append(f"  - Limitations: {'; '.join(limitations)}")

    return "\n".join(lines)


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

    context = "\n".join(ranked_docs[:3])

    corpus_context = _load_rag_corpus_text()
    if corpus_context:
        context = f"{corpus_context}\n\nRetrieved passages:\n{context}"

    with open(prompts_path, encoding="utf-8") as file:
        prompts = yaml.safe_load(file)
        rag_template = prompts.get("rag_prompt", "")

    if not rag_template:
        raise RuntimeError("RAG prompt template not found in prompts.yaml")

    prompt = rag_template.format(context=context, query=query)

    client = ollama.Client(host="http://ollama:11434")
    response = client.generate(model=LLM_MODEL, prompt=prompt, options={"temperature": 0.0})

    return response["response"]
