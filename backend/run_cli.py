"""Run the graph without the UI — a quick sanity check.

Usage:  python run_cli.py ../samples/deployment_regression.log
"""
import asyncio
import sys

from app.graph import graph
from app.knowledge.runbook_store import seed_if_empty


async def main(path: str) -> None:
    seed_if_empty()
    raw = open(path, encoding="utf-8").read()
    cfg = {"configurable": {"thread_id": "cli-1"}}
    async for chunk in graph.astream({"raw_logs": raw, "trace": []}, cfg, stream_mode="updates"):
        for node, update in chunk.items():
            for ev in update.get("trace", []):
                print(f"[{node}] {ev['message']}")

    final = graph.get_state(cfg).values
    print("\n--- SLACK PREVIEW ---")
    slack = final.get("slack_result")
    if slack:
        print(slack.get("text_preview") if isinstance(slack, dict) else slack.text_preview)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "../samples/deployment_regression.log"
    asyncio.run(main(target))