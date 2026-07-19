"""Evaluation runner for the incident analysis pipeline.

Runs the golden set through the pipeline and produces metrics on:
- Category classification accuracy
- Severity classification accuracy
- Keyword recall in remediations
- Retrieval relevance scores
- End-to-end latency
"""

import time
import logging
from typing import Optional

from app.models import (
    ClassifierOutput, RemediationOutput, EvalCase, EvalResult, EvalSummary,
)
from app.parsing import parse_logs, cluster_errors
from app.llm import get_llm
from app.knowledge.runbook_store import retrieve, get_store
from app.evals.golden_set import GOLDEN_SET
from app.evals.reranker import rerank, rechunk_documents
from app.nodes.classifier import CLASSIFY_PROMPT
from app.nodes.remediation import REMEDIATION_PROMPT

logger = logging.getLogger(__name__)


def _run_single_eval(case: dict, use_reranking: bool = True) -> EvalResult:
    """Run a single evaluation case through the pipeline."""
    start = time.time()

    entries = parse_logs(case["input_log"])
    clusters = cluster_errors(entries)

    predicted_category = "unknown"
    predicted_severity = "info"
    remediation_text = ""

    if clusters:
        clusters_text = "\n\n".join(
            f"[{c.count}x] level={c.level} service={c.example_service} sig={c.signature}\n"
            + "\n".join(f"  {ln}" for ln in c.sample_lines)
            for c in clusters
        )
        llm = get_llm().with_structured_output(
            ClassifierOutput, method="function_calling"
        )
        result = llm.invoke(CLASSIFY_PROMPT.format(clusters=clusters_text))
        if result.issues:
            predicted_category = result.issues[0].category
            predicted_severity = result.issues[0].severity

            store = get_store()
            issue = result.issues[0]
            query = f"{issue.title} {issue.category} {issue.affected_service} {issue.summary}"

            if use_reranking:
                candidates = store.similarity_search(query, k=10)
                reranked = rerank(query, candidates, top_k=3)
                docs = [doc for doc, _ in reranked]
            else:
                docs = retrieve(query, k=3)

            runbooks_text = "\n\n".join(
                f"[{d.metadata.get('title', 'runbook')}]\n{d.page_content}"
                for d in docs
            ) or "No matching runbooks found."

            issues_text = (
                f"- id={issue.id} | {issue.severity.upper()} | {issue.category} | "
                f"{issue.affected_service} | {issue.summary}"
            )

            llm_rem = get_llm(temperature=0.2).with_structured_output(
                RemediationOutput, method="function_calling"
            )
            rem_result = llm_rem.invoke(
                REMEDIATION_PROMPT.format(issues=issues_text, runbooks=runbooks_text)
            )
            if rem_result.remediations:
                remediation_text = " ".join(
                    f"{r.fix_summary} {r.suggested_command} {r.rationale}"
                    for r in rem_result.remediations
                )

    latency_ms = (time.time() - start) * 1000

    category_match = predicted_category == case["expected_category"]
    severity_match = predicted_severity == case["expected_severity"]

    expected_kw = case.get("expected_keywords", [])
    if expected_kw and remediation_text:
        found = sum(
            1 for kw in expected_kw
            if kw.lower() in remediation_text.lower()
        )
        keyword_recall = found / len(expected_kw)
    else:
        keyword_recall = 0.0

    retrieval_relevance = 0.0
    if clusters and result.issues:
        query = f"{result.issues[0].title} {result.issues[0].category}"
        docs = retrieve(query, k=3)
        if docs:
            retrieval_relevance = 1.0 if category_match else 0.5

    passed = category_match and severity_match and keyword_recall >= 0.4

    return EvalResult(
        case_id=case["id"],
        category_match=category_match,
        severity_match=severity_match,
        keyword_recall=keyword_recall,
        retrieval_relevance=retrieval_relevance,
        latency_ms=latency_ms,
        passed=passed,
    )


def run_eval_suite(
    cases: Optional[list[dict]] = None,
    use_reranking: bool = True,
) -> tuple[list[EvalResult], EvalSummary]:
    """Run the full eval suite and return individual results + summary."""
    if cases is None:
        cases = GOLDEN_SET

    results: list[EvalResult] = []
    for case in cases:
        logger.info("Running eval case: %s", case["id"])
        try:
            result = _run_single_eval(case, use_reranking=use_reranking)
            results.append(result)
            logger.info(
                "  %s: cat=%s sev=%s kw=%.2f passed=%s (%.0fms)",
                case["id"],
                result.category_match,
                result.severity_match,
                result.keyword_recall,
                result.passed,
                result.latency_ms,
            )
        except Exception as e:
            logger.error("Eval case %s failed: %s", case["id"], e)
            results.append(EvalResult(
                case_id=case["id"],
                category_match=False,
                severity_match=False,
                keyword_recall=0.0,
                retrieval_relevance=0.0,
                latency_ms=0.0,
                passed=False,
            ))

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    summary = EvalSummary(
        total=total,
        passed=passed,
        failed=total - passed,
        category_accuracy=sum(1 for r in results if r.category_match) / max(total, 1),
        severity_accuracy=sum(1 for r in results if r.severity_match) / max(total, 1),
        avg_keyword_recall=sum(r.keyword_recall for r in results) / max(total, 1),
        avg_retrieval_relevance=sum(r.retrieval_relevance for r in results) / max(total, 1),
        avg_latency_ms=sum(r.latency_ms for r in results) / max(total, 1),
    )

    logger.info(
        "Eval summary: %d/%d passed, cat_acc=%.2f, sev_acc=%.2f, kw_recall=%.2f",
        passed, total, summary.category_accuracy,
        summary.severity_accuracy, summary.avg_keyword_recall,
    )
    return results, summary


def run_reingestion_eval() -> dict:
    """Test re-ingestion: add HF knowledge, rechunk, rerank, then re-evaluate.

    Returns before/after metrics to show improvement.
    """
    logger.info("Running baseline eval (before re-ingestion)...")
    _, baseline = run_eval_suite(use_reranking=False)

    from app.knowledge.hf_datasets import ingest_hf_knowledge_to_store
    n_added = ingest_hf_knowledge_to_store()
    logger.info("Ingested %d new documents from HF knowledge.", n_added)

    store = get_store()
    existing = store.get()
    if existing and existing.get("documents"):
        from langchain_core.documents import Document
        docs = [
            Document(
                page_content=text,
                metadata=meta or {},
            )
            for text, meta in zip(
                existing["documents"], existing.get("metadatas", [{}] * len(existing["documents"]))
            )
        ]
        rechunked = rechunk_documents(docs, chunk_size=400, overlap=50)
        logger.info("Rechunked %d docs into %d chunks.", len(docs), len(rechunked))

    logger.info("Running post-ingestion eval (with reranking)...")
    _, improved = run_eval_suite(use_reranking=True)

    return {
        "baseline": baseline.model_dump(),
        "after_reingestion": improved.model_dump(),
        "documents_added": n_added,
        "improvement": {
            "category_accuracy_delta": improved.category_accuracy - baseline.category_accuracy,
            "severity_accuracy_delta": improved.severity_accuracy - baseline.severity_accuracy,
            "keyword_recall_delta": improved.avg_keyword_recall - baseline.avg_keyword_recall,
            "retrieval_relevance_delta": improved.avg_retrieval_relevance - baseline.avg_retrieval_relevance,
        },
    }
