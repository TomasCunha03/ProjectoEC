"""
RAG (Retrieval-Augmented Generation) pipeline module.

Implements a two-stage retrieve-then-rerank pipeline backed by ChromaDB:

1. Embed the user query with ``BAAI/bge-base-en-v1.5`` and retrieve candidate
   passages from all configured Chroma collections.
2. Rerank the candidates with ``BAAI/bge-reranker-base`` (a cross-encoder) and
   keep only the top-3 passages as context.
3. Inject the passages plus optional corpus metadata into a prompt template from
   ``prompts.yaml`` and generate a final answer via a local Ollama LLM.

Both the embedding model and the reranker are loaded lazily so that importing
this module does not delay API startup when the RAG tool is not the first one
used in a session.
"""

import os
import time

import ollama
import yaml
from sentence_transformers import CrossEncoder, SentenceTransformer

from chat_saude.infrastructure.database.chroma import get_chroma_client
from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

COLLECTION_NAMES = ["pmc_medicine_preventive", "home_remedies"]

# Lazy-loaded to avoid blocking API startup on first boot
_embedding_model = None
_reranker = None


def _get_embedding_model():
    """Return the sentence-transformer embedding model, loading it on first call."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model BAAI/bge-base-en-v1.5...")
        _embedding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
        logger.info("Embedding model loaded")
    return _embedding_model


def _get_reranker():
    """Return the cross-encoder reranker model, loading it on first call."""
    global _reranker
    if _reranker is None:
        logger.info("Loading reranker model BAAI/bge-reranker-base...")
        _reranker = CrossEncoder("BAAI/bge-reranker-base")
        logger.info("Reranker model loaded")
    return _reranker


chroma_client = get_chroma_client()
collections = [chroma_client.get_or_create_collection(name=name) for name in COLLECTION_NAMES]

LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:1.5b")

# Load rag_prompt from prompts.yaml (src/chat_saude/rag: .. -> chat_saude, .. -> src, agents)
agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agents"))
prompts_path = os.path.join(agents_dir, "prompts.yaml")
rag_corpus_path = os.path.join(agents_dir, "rag_corpus.yaml")


def _load_rag_corpus_text() -> str:
    """Read corpus metadata from ``rag_corpus.yaml`` and format it as plain text.

    This metadata is prepended to the retrieved passages so the LLM understands
    the nature and limitations of the knowledge base it is drawing from.
    Returns an empty string if the file is missing or unreadable, which is
    treated as a no-op by the caller.
    """
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
    """Run the full RAG pipeline for *query* and return the LLM-generated answer.

    Steps:
      1. Encode the query into a dense vector.
      2. Retrieve the top-3 candidate passages from each Chroma collection.
      3. Rerank all candidates with a cross-encoder and keep the top 3.
      4. Build a prompt from the ranked context and the template in prompts.yaml.
      5. Generate and return the answer via Ollama with temperature=0 for
         deterministic, fact-grounded responses.

    Raises ``RuntimeError`` if the RAG prompt template is missing from
    ``prompts.yaml``, as the pipeline cannot continue without it.
    """
    logger.info("RAG pipeline start: query=%s", query[:80])

    # Encode query to a dense vector for ChromaDB similarity search.
    emb = _get_embedding_model().encode(query).tolist()

    # Retrieve candidate passages from every configured collection.
    all_docs = []

    for collection in collections:
        results = collection.query(query_embeddings=[emb], n_results=3)

        docs = results["documents"][0]
        all_docs.extend(docs)

    logger.info("RAG retrieved %d docs", len(all_docs))

    # Cross-encoder reranking: score every (query, passage) pair jointly so
    # that semantic relevance is judged in full context, not just by embedding
    # cosine similarity.
    pairs = [(query, d) for d in all_docs]
    scores = _get_reranker().predict(pairs)

    ranked_docs = [d for _, d in sorted(zip(scores, all_docs), reverse=True)]

    # Use only the top-3 passages to keep the context window manageable.
    context = "\n".join(ranked_docs[:3])

    corpus_context = _load_rag_corpus_text()
    if corpus_context:
        # Prepend corpus metadata so the LLM knows the provenance of the passages.
        context = f"{corpus_context}\n\nRetrieved passages:\n{context}"

    with open(prompts_path, encoding="utf-8") as file:
        prompts = yaml.safe_load(file)
        rag_template = prompts.get("rag_prompt", "")

    if not rag_template:
        raise RuntimeError("RAG prompt template not found in prompts.yaml")

    prompt = rag_template.format(context=context, query=query)

    # temperature=0.0 makes responses deterministic and reduces hallucination risk.
    client = ollama.Client(host="http://ollama:11434")
    t0 = time.perf_counter()
    response = client.generate(model=LLM_MODEL, prompt=prompt, options={"temperature": 0.0})
    elapsed = time.perf_counter() - t0
    logger.info("RAG LLM response in %.2fs model=%s", elapsed, LLM_MODEL)

    return response["response"]
