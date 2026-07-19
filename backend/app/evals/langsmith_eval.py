"""LangSmith integration for evaluation tracking.

Wraps the eval pipeline with LangSmith tracing so that every eval run,
individual case, LLM call, and retrieval step is recorded and viewable
in the LangSmith dashboard.
"""

import os
import time
import logging
from typing import Optional

from app.evals.evaluator import run_eval_suite
from app.evals.golden_set import GOLDEN_SET

logger = logging.getLogger(__name__)

LANGSMITH_AVAILABLE = False


def _check_langsmith() -> bool:
    global LANGSMITH_AVAILABLE
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    if not api_key:
        logger.info("LANGSMITH_API_KEY not set — eval tracking runs locally only.")
        return False
    try:
        from langsmith import Client
        _ = Client()
        LANGSMITH_AVAILABLE = True
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault(
            "LANGCHAIN_PROJECT", os.getenv("LANGSMITH_PROJECT", "incident-suite-evals")
        )
        logger.info("LangSmith tracing enabled for project: %s", os.environ["LANGCHAIN_PROJECT"])
        return True
    except Exception as e:
        logger.warning("LangSmith init failed: %s", e)
        return False


def configure_langsmith(
    api_key: Optional[str] = None,
    project: str = "incident-suite-evals",
    endpoint: str = "https://api.smith.langchain.com",
) -> dict:
    """Configure LangSmith tracing environment.

    Returns a dict indicating whether LangSmith is active and the project name.
    """
    if api_key:
        os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project
    os.environ["LANGCHAIN_ENDPOINT"] = endpoint

    active = _check_langsmith()
    return {
        "active": active,
        "project": project,
        "endpoint": endpoint,
    }


def create_langsmith_dataset(
    dataset_name: str = "incident-suite-golden-set",
    cases: Optional[list[dict]] = None,
) -> dict:
    """Create or update a LangSmith dataset from golden set test cases.

    Each case becomes an example with inputs (log text) and expected outputs
    (category, severity, keywords).
    """
    if cases is None:
        cases = GOLDEN_SET

    if not _check_langsmith():
        return {
            "status": "skipped",
            "reason": "LangSmith not configured",
            "cases_count": len(cases),
        }

    try:
        from langsmith import Client

        client = Client()

        try:
            dataset = client.create_dataset(
                dataset_name=dataset_name,
                description="Golden set for incident analysis pipeline evaluation",
            )
        except Exception:
            datasets = list(client.list_datasets(dataset_name=dataset_name))
            if datasets:
                dataset = datasets[0]
            else:
                raise

        for case in cases:
            client.create_example(
                inputs={
                    "input_log": case["input_log"],
                    "description": case.get("description", ""),
                },
                outputs={
                    "expected_category": case["expected_category"],
                    "expected_severity": case["expected_severity"],
                    "expected_keywords": case.get("expected_keywords", []),
                },
                dataset_id=dataset.id,
            )

        return {
            "status": "created",
            "dataset_name": dataset_name,
            "dataset_id": str(dataset.id),
            "examples_count": len(cases),
        }
    except Exception as e:
        logger.error("Failed to create LangSmith dataset: %s", e)
        return {"status": "error", "error": str(e)}


def run_langsmith_eval(
    dataset_name: str = "incident-suite-golden-set",
    experiment_name: Optional[str] = None,
    use_reranking: bool = True,
) -> dict:
    """Run eval suite with LangSmith tracking.

    All LLM calls, retrieval steps, and scoring are automatically traced
    to LangSmith when configured. The eval summary is also logged as
    a custom run.
    """
    ls_active = _check_langsmith()

    if experiment_name is None:
        experiment_name = f"eval-{int(time.time())}"

    if ls_active:
        os.environ["LANGCHAIN_PROJECT"] = experiment_name

    results, summary = run_eval_suite(use_reranking=use_reranking)

    output = {
        "experiment_name": experiment_name,
        "langsmith_tracked": ls_active,
        "summary": summary.model_dump(),
        "results": [r.model_dump() for r in results],
    }

    if ls_active:
        try:
            from langsmith import Client
            client = Client()
            _log_eval_feedback(client, experiment_name, results, summary)
        except Exception as e:
            logger.warning("Failed to log eval feedback to LangSmith: %s", e)

    return output


def _log_eval_feedback(client, experiment_name: str, results, summary):
    """Log evaluation metrics as LangSmith feedback."""
    try:
        from langsmith.run_trees import RunTree

        root = RunTree(
            name=experiment_name,
            run_type="chain",
            inputs={"eval_type": "golden_set", "total_cases": summary.total},
            project_name=os.environ.get("LANGCHAIN_PROJECT", "incident-suite-evals"),
        )

        root.end(
            outputs={
                "total": summary.total,
                "passed": summary.passed,
                "failed": summary.failed,
                "category_accuracy": summary.category_accuracy,
                "severity_accuracy": summary.severity_accuracy,
                "avg_keyword_recall": summary.avg_keyword_recall,
                "avg_retrieval_relevance": summary.avg_retrieval_relevance,
                "avg_latency_ms": summary.avg_latency_ms,
            },
        )
        root.post()
        logger.info("Logged eval run '%s' to LangSmith.", experiment_name)
    except Exception as e:
        logger.warning("RunTree logging failed: %s", e)


def run_comparison_eval(
    baseline_reranking: bool = False,
    improved_reranking: bool = True,
) -> dict:
    """Run two eval passes and compare — useful for A/B testing changes.

    Returns both summaries side-by-side with deltas.
    """
    logger.info("Running baseline eval (reranking=%s)...", baseline_reranking)
    _, baseline = run_eval_suite(use_reranking=baseline_reranking)

    logger.info("Running improved eval (reranking=%s)...", improved_reranking)
    _, improved = run_eval_suite(use_reranking=improved_reranking)

    return {
        "baseline": baseline.model_dump(),
        "improved": improved.model_dump(),
        "deltas": {
            "category_accuracy": improved.category_accuracy - baseline.category_accuracy,
            "severity_accuracy": improved.severity_accuracy - baseline.severity_accuracy,
            "avg_keyword_recall": improved.avg_keyword_recall - baseline.avg_keyword_recall,
            "avg_retrieval_relevance": improved.avg_retrieval_relevance - baseline.avg_retrieval_relevance,
            "avg_latency_ms": improved.avg_latency_ms - baseline.avg_latency_ms,
        },
    }
