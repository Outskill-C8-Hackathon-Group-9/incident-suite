"""Hybrid retrieval: BM25 + vector search fused with Reciprocal Rank Fusion (RRF).

Rebuild the BM25 index whenever the corpus changes (seed, ingest, feedback).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_bm25 = None
_bm25_docs: list[Document] = []
_tokenized_corpus: list[list[str]] = []


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_./-]+", text.lower())


def rebuild_bm25_index(documents: list[Document]) -> int:
    """Rebuild the in-memory BM25 index from the given documents."""
    global _bm25, _bm25_docs, _tokenized_corpus

    if not documents:
        _bm25 = None
        _bm25_docs = []
        _tokenized_corpus = []
        return 0

    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning("rank_bm25 not installed; hybrid search disabled.")
        _bm25 = None
        _bm25_docs = []
        _tokenized_corpus = []
        return 0

    _bm25_docs = list(documents)
    _tokenized_corpus = [_tokenize(d.page_content) for d in _bm25_docs]
    _bm25 = BM25Okapi(_tokenized_corpus)
    logger.info("BM25 index rebuilt with %d documents.", len(_bm25_docs))
    return len(_bm25_docs)


def bm25_search(query: str, k: int = 10) -> list[tuple[Document, float]]:
    """Return top-k BM25 hits as (document, score) pairs."""
    if _bm25 is None or not _bm25_docs:
        return []

    tokens = _tokenize(query)
    if not tokens:
        return []

    scores = _bm25.get_scores(tokens)
    ranked = sorted(
        enumerate(scores),
        key=lambda x: x[1],
        reverse=True,
    )[:k]
    return [(_bm25_docs[i], float(score)) for i, score in ranked if score > 0]


def reciprocal_rank_fusion(
    ranked_lists: list[list[Document]],
    k: int = 10,
    rrf_k: int = 60,
) -> list[Document]:
    """Merge multiple ranked document lists using RRF."""
    scores: dict[str, float] = {}
    docs_by_key: dict[str, Document] = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked):
            key = _doc_key(doc)
            docs_by_key[key] = doc
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [docs_by_key[key] for key, _ in ordered[:k]]


def _doc_key(doc: Document) -> str:
    title = doc.metadata.get("title", "")
    chunk = doc.metadata.get("chunk_index", "")
    # Prefer content fingerprint so duplicate titles across sources stay distinct.
    return f"{title}|{chunk}|{hash(doc.page_content[:200])}"


def hybrid_search(
    query: str,
    vector_docs: list[Document],
    k: int = 10,
) -> list[Document]:
    """Fuse BM25 and vector candidate lists via RRF."""
    bm25_hits = [doc for doc, _ in bm25_search(query, k=k)]
    if not bm25_hits:
        return vector_docs[:k]
    if not vector_docs:
        return bm25_hits[:k]
    return reciprocal_rank_fusion([vector_docs, bm25_hits], k=k)


def index_ready() -> bool:
    return _bm25 is not None and bool(_bm25_docs)
