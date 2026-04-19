import os
import time

import ollama
import yaml
from sentence_transformers import CrossEncoder, SentenceTransformer

from chat_saude.config.settings import settings
from chat_saude.infrastructure.database.chroma import get_chroma_client
from chat_saude.observability.langfuse_client import end_span, start_span, tracing_active
from chat_saude.observability.logger import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "pmc_medicine_preventive"

embedding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
reranker = CrossEncoder("BAAI/bge-reranker-base")

chroma_client = get_chroma_client()


def _rag_collection():
    """
    Resolve the collection handle on each query.

    Ingestion deletes/recreates `COLLECTION_NAME`; a module-level Collection object would go stale and
    can return empty results or error until the API process restarts.
    """
    return chroma_client.get_or_create_collection(name=COLLECTION_NAME)

LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:1b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434").rstrip("/")

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


def _chroma_query(query: str, n_results: int) -> tuple[list[str], dict]:
    """Run embedding + Chroma query; return documents and a Langfuse-friendly retrieval summary."""
    # Must match ingestion (chromadb_ingest.py): normalized embeddings for BGE + Chroma cosine/L2 search.
    emb = embedding_model.encode(query, normalize_embeddings=True).tolist()
    coll = _rag_collection()
    try:
        approx_count = coll.count()
    except Exception:
        approx_count = None
    results = coll.query(query_embeddings=[emb], n_results=n_results)
    docs = results["documents"][0]
    ids = (results.get("ids") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]

    initial_hits: list[dict] = []
    for i, doc in enumerate(docs):
        initial_hits.append(
            {
                "chroma_rank": i + 1,
                "id": ids[i] if i < len(ids) else None,
                "distance": float(distances[i]) if i < len(distances) and distances[i] is not None else None,
                "document_preview": doc[:2000],
                "metadata": metadatas[i] if i < len(metadatas) else None,
            }
        )

    summary = {
        "embedding_model": "BAAI/bge-base-en-v1.5",
        "query_normalize_embeddings": True,
        "chroma_host": settings.VECTOR_DB_HOST,
        "chroma_port": settings.VECTOR_DB_PORT,
        "collection": COLLECTION_NAME,
        "collection_document_count": approx_count,
        "n_results_requested": n_results,
        "n_documents_returned": len(docs),
        "initial_hits": initial_hits,
    }
    return docs, summary


def _rerank_passages(query: str, docs: list[str]) -> tuple[str, list[dict]]:
    pairs = [(query, d) for d in docs]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, docs), key=lambda x: float(x[0]), reverse=True)

    top_k = ranked[:3]
    ranked_docs = [d for _, d in top_k]
    rerank_detail = []
    for rank, (score, doc) in enumerate(top_k, start=1):
        rerank_detail.append(
            {
                "rank_after_rerank": rank,
                "cross_encoder_score": float(score),
                "text_preview": doc[:2500],
            }
        )

    passages = "\n".join(ranked_docs)
    return passages, rerank_detail


def rag_answer_detailed(query: str) -> dict:
    """
    Full RAG step with structured retrieval metadata for observability (e.g. Langfuse).

    Keys: answer (str), retrieval (dict), llm (dict).
    """
    logger.info("RAG pipeline start: query=%s", query[:80])
    n_results = 5

    span_retrieval = None
    if tracing_active():
        span_retrieval = start_span(
            name="rag_chroma_retrieval",
            input_payload={
                "query": query,
                "collection": COLLECTION_NAME,
                "n_results": n_results,
            },
        )

    try:
        docs, chroma_summary = _chroma_query(query, n_results)
        logger.info("RAG retrieved %d docs", len(docs))
        if span_retrieval is not None:
            end_span(span_retrieval, output_payload={"chroma": chroma_summary})
    except Exception as exc:
        logger.exception("Chroma retrieval failed")
        if span_retrieval is not None:
            end_span(
                span_retrieval,
                output_payload={
                    "error": "chroma_query_failed",
                    "exception_type": type(exc).__name__,
                    "detail": str(exc),
                    "chroma_host": settings.VECTOR_DB_HOST,
                    "chroma_port": settings.VECTOR_DB_PORT,
                },
                level="ERROR",
                status_message="rag_chroma_failed",
            )
        raise

    span_rerank = None
    if tracing_active():
        span_rerank = start_span(
            name="rag_cross_encoder_rerank",
            input_payload={"query": query, "candidate_count": len(docs)},
        )

    try:
        passages, rerank_chunks = _rerank_passages(query, docs)
        if span_rerank is not None:
            end_span(
                span_rerank,
                output_payload={
                    "reranker_model": "BAAI/bge-reranker-base",
                    "top_k_used_for_context": 3,
                    "ranked_chunks": rerank_chunks,
                },
            )
    except Exception:
        if span_rerank is not None:
            end_span(
                span_rerank,
                output_payload={"error": "rerank_failed"},
                level="ERROR",
                status_message="rag_rerank_failed",
            )
        raise

    corpus_context = _load_rag_corpus_text()

    if corpus_context:
        context = (
            "=== Corpus metadata (scope and coverage — for your reasoning only; "
            "never quote collection names, labels, or system details to the user) ===\n"
            f"{corpus_context}\n\n"
            "=== Retrieved excerpts (use for substantive answer when relevant) ===\n"
            f"{passages}"
        )
    else:
        context = passages

    with open(prompts_path, encoding="utf-8") as file:
        prompts = yaml.safe_load(file)
        rag_template = prompts.get("rag_prompt", "")

    if not rag_template:
        raise RuntimeError("RAG prompt template not found in prompts.yaml")

    prompt = rag_template.format(context=context, query=query)

    span_llm = None
    if tracing_active():
        span_llm = start_span(
            name="rag_ollama_generate",
            input_payload={
                "query": query,
                "model": LLM_MODEL,
                "temperature": 0.0,
                "prompt_chars": len(prompt),
                "context_chars": len(context),
            },
        )

    try:
        client = ollama.Client(host=OLLAMA_HOST)
        t0 = time.perf_counter()
        response = client.generate(model=LLM_MODEL, prompt=prompt, options={"temperature": 0.0})
        elapsed = time.perf_counter() - t0
        logger.info("RAG LLM response in %.2fs model=%s", elapsed, LLM_MODEL)

        answer_text = response["response"]
        llm_meta = {
            "model": LLM_MODEL,
            "latency_s": round(elapsed, 4),
            "prompt_chars": len(prompt),
            "answer_chars": len(answer_text),
        }

        if span_llm is not None:
            end_span(span_llm, output_payload={"answer_preview": answer_text[:4000], **llm_meta})
    except Exception:
        if span_llm is not None:
            end_span(
                span_llm,
                output_payload={"error": "ollama_generate_failed"},
                level="ERROR",
                status_message="rag_llm_failed",
            )
        raise

    retrieval_bundle = {
        "search_query": query,
        "chroma": chroma_summary,
        "reranked_top_chunks": rerank_chunks,
        "context_chars": len(context),
    }

    return {
        "answer": answer_text,
        "retrieval": retrieval_bundle,
        "llm": llm_meta,
    }


def rag_answer(query: str) -> str:
    return rag_answer_detailed(query)["answer"]
