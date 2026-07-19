"""Run the graph without the UI — a quick sanity check.

Usage:
  python run_cli.py ../samples/deployment_regression.log
  python run_cli.py --eval                    # run golden set evals
  python run_cli.py --image-test              # test image analysis
  python run_cli.py --reingestion             # test HF reingestion flow
"""
import asyncio
import sys
import json

from app.graph import graph
from app.knowledge.runbook_store import seed_if_empty
from app.knowledge.hf_datasets import ingest_hf_knowledge_to_store


async def run_analysis(path: str) -> None:
    raw = open(path, encoding="utf-8").read()
    cfg = {"configurable": {"thread_id": "cli-1"}}
    initial = {"raw_logs": raw, "trace": []}
    async for chunk in graph.astream(initial, cfg, stream_mode="updates"):
        for node, update in chunk.items():
            for ev in update.get("trace", []):
                print(f"[{node}] {ev['message']}")

    final = graph.get_state(cfg).values
    print("\n--- SLACK PREVIEW ---")
    slack = final.get("slack_result")
    if slack:
        print(slack.get("text_preview") if isinstance(slack, dict) else slack.text_preview)

    if final.get("fallback_results"):
        print("\n--- FALLBACK RESULTS ---")
        fb = final["fallback_results"]
        print(f"Processed: {fb.get('processed', 0)} issues")
        print(f"New remediations: {fb.get('new_remediations', 0)}")
        print(f"Patterns learned: {fb.get('patterns_learned', 0)}")
        for score in fb.get("eval_scores", []):
            print(f"  [{score['issue_id']}] relevance={score.get('relevance_score', 0):.3f}")


def run_evals() -> None:
    from app.evals.evaluator import run_eval_suite
    print("Running golden set evals...\n")
    results, summary = run_eval_suite(use_reranking=True)

    print(f"{'Case':<15} {'Cat':>5} {'Sev':>5} {'KW%':>6} {'Ret%':>6} {'ms':>8} {'Pass':>6}")
    print("-" * 55)
    for r in results:
        print(
            f"{r.case_id:<15} "
            f"{'Y' if r.category_match else 'N':>5} "
            f"{'Y' if r.severity_match else 'N':>5} "
            f"{r.keyword_recall*100:>5.0f}% "
            f"{r.retrieval_relevance*100:>5.0f}% "
            f"{r.latency_ms:>7.0f} "
            f"{'PASS' if r.passed else 'FAIL':>6}"
        )

    print(f"\n--- SUMMARY ---")
    print(f"Total: {summary.total} | Passed: {summary.passed} | Failed: {summary.failed}")
    print(f"Category accuracy: {summary.category_accuracy:.1%}")
    print(f"Severity accuracy: {summary.severity_accuracy:.1%}")
    print(f"Avg keyword recall: {summary.avg_keyword_recall:.1%}")
    print(f"Avg retrieval relevance: {summary.avg_retrieval_relevance:.1%}")
    print(f"Avg latency: {summary.avg_latency_ms:.0f}ms")


def run_image_test() -> None:
    from app.nodes.image_analyzer import analyze_image_with_vision, TEST_IMAGE

    print("Testing image analysis with test image description...\n")
    analysis = analyze_image_with_vision(
        description=TEST_IMAGE["description"],
    )
    print(f"Description: {analysis.description}")
    print(f"Category: {analysis.category} (expected: {TEST_IMAGE['expected_category']})")
    print(f"Severity: {analysis.severity} (expected: {TEST_IMAGE['expected_severity']})")
    print(f"Confidence: {analysis.confidence:.0%}")
    print(f"Detected errors: {analysis.detected_errors}")
    print(f"Resolution steps:")
    for i, step in enumerate(analysis.resolution_steps, 1):
        print(f"  {i}. {step}")


def run_reingestion_test() -> None:
    from app.evals.evaluator import run_reingestion_eval

    print("Running re-ingestion evaluation...\n")
    result = run_reingestion_eval()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    seed_if_empty()
    ingest_hf_knowledge_to_store()

    if "--eval" in sys.argv:
        run_evals()
    elif "--image-test" in sys.argv:
        run_image_test()
    elif "--reingestion" in sys.argv:
        run_reingestion_test()
    else:
        target = sys.argv[1] if len(sys.argv) > 1 else "../samples/deployment_regression.log"
        asyncio.run(run_analysis(target))
