import logging
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from app.config import config
from app.knowledge.runbook_seed import RUNBOOKS

logger = logging.getLogger(__name__)

_embeddings: HuggingFaceEmbeddings | None = None
_store: Chroma | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        # First call downloads the model once (~90MB), then runs locally/offline.
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
    """Return the top-k most similar runbooks for a query string."""
    store = get_store()
    return store.similarity_search(query, k=k or config.RAG_TOP_K)