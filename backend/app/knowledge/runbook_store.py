import logging
import os
from typing import Union

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFaceEndpointEmbeddings
from langchain_core.documents import Document

from app.config import config
from app.knowledge.runbook_seed import RUNBOOKS

logger = logging.getLogger(__name__)

_embeddings: Union[HuggingFaceEmbeddings, HuggingFaceEndpointEmbeddings, None] = None
_store: Chroma | None = None


def _get_embeddings() -> Union[HuggingFaceEmbeddings, HuggingFaceEndpointEmbeddings]:
    global _embeddings
    if _embeddings is None:
        hf_token = os.getenv("HF_TOKEN", "")
        if hf_token:
            # Production (Render): use HF Inference API — no local model download.
            # This avoids loading PyTorch + sentence-transformers (~400MB) locally,
            # keeping RAM well within the 512MB free-tier limit.
            logger.info("[embeddings] Using HuggingFace Inference API (HF_TOKEN set).")
            _embeddings = HuggingFaceEndpointEmbeddings(
                model=config.EMBEDDING_MODEL,
                huggingfacehub_api_token=hf_token,
            )
        else:
            # Local dev: download + run the model on this machine.
            logger.info("[embeddings] Using local sentence-transformers (no HF_TOKEN).")
            _embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    return _embeddings


def get_store() -> Chroma:
    global _store
    if _store is None:
        _store = Chroma(
            collection_name="runbooks",
            embedding_function=_get_embeddings(),
            persist_directory=config.CHROMA_DIR,
        )
    return _store


def seed_if_empty() -> int:
    """Populate the vector DB with the curated runbook corpus if it's empty.

    Returns the number of documents added (0 if already seeded).
    """
    store = get_store()
    existing = store.get()  # {'ids': [...], ...}
    if existing and existing.get("ids"):
        logger.info("Runbook store already seeded (%d docs).", len(existing["ids"]))
        return 0

    docs = [
        Document(
            page_content=rb["content"],
            metadata={
                "title": rb["title"],
                "category": rb["category"],
                "service_hint": rb.get("service_hint", ""),
            },
        )
        for rb in RUNBOOKS
    ]
    store.add_documents(docs)
    logger.info("Seeded runbook store with %d docs.", len(docs))
    return len(docs)


def retrieve(query: str, k: int | None = None) -> list[Document]:
    """Return the top-k most similar runbooks for a query string, excluding
    weak matches (Chroma's plain similarity_search always returns k docs
    regardless of relevance, which would make every issue a "hit" and the
    investigative path unreachable). Lower distance = more similar."""
    store = get_store()
    scored = store.similarity_search_with_score(query, k=k or config.RAG_TOP_K)
    return [doc for doc, distance in scored if distance <= config.RAG_MAX_DISTANCE]


def add_runbook(*, title: str, category: str, content: str) -> None:
    """Ingest a resolved incident as a new runbook so future occurrences of the
    same error are grounded (cookbook/RAG hit) instead of going investigative."""
    if not content:
        return
    store = get_store()
    store.add_documents([
        Document(
            page_content=content,
            metadata={"title": title, "category": category or "unknown", "service_hint": ""},
        )
    ])
    logger.info("Ingested resolved incident '%s' into the runbook store.", title)