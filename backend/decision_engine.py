# =====================================================================
# ASCII Data Flow Diagram
# =====================================================================
#
#  CLI wrapper around the decision engine. Reads a signals JSON file
#  (produced by the upstream cookbook + RAG blocks), coerces it into a
#  SourceSignals object, runs decide(), and prints the chosen path as
#  JSON to stdout.
#
#                  +-------------------+
#                  |   CLI Argument    |
#                  |  (signals JSON)   |
#                  +---------+---------+
#                            |
#                            v
#                  +---------+---------+
#                  |   build_parser()  |
#                  +---------+---------+
#                            |
#                            v
#                  +---------+---------+
#                  |      main()       |
#                  +---------+---------+
#                            |
#                            v
#        +-------------------+-------------------+
#        |                                       |
#        v                                       v
# +-------------+-------------+   +------------------------------+
# |  Path(args.input)         |   |  json.loads(...)             |
# |  .read_text()             |   |  (parse signals JSON)        |
# |  (read raw JSON)          |   |                              |
# +-------------+-------------+   +------------------------------+
#                |                              |
#                +--------------+---------------+
#                               |
#                               v
#                +--------------+--------------+
#                |  _coerce_signals(payload)   |
#                |  (dict -> SourceSignals)    |
#                +--------------+--------------+
#                               |
#                               v
#                +--------------+--------------+
#                |   decide(signals)           |
#                |  (app.decision_engine)      |
#                +--------------+--------------+
#                               |
#                               v
#                +--------------+--------------+
#                | decision.model_dump()       |
#                +--------------+--------------+
#                               |
#                               v
#                +--------------+--------------+
#                |   JSON -> stdout            |
#                |   {"ok": true, "decision":  |
#                |    {...}}                   |
#                +-----------------------------+
#
#  Note: The CLI input contract is intentionally small (cookbook_hits,
#  rag_hits, severity, summary) so it remains decoupled from whatever
#  shape the upstream parsing/lookup blocks eventually settle on.
# =====================================================================

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.decision_engine import decide_from_payload


# Build the CLI argument parser for the decision engine.
# Accepts one positional argument: the path to a signals JSON file.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the incident decision engine on cookbook/RAG signals."
    )
    parser.add_argument(
        "input",
        help=(
            "Path to a JSON file with cookbook_hits, rag_hits, "
            "severity, and summary."
        ),
    )
    return parser


# Orchestrator: parse CLI args, load and coerce the signals JSON,
# invoke the decision engine, and emit the result as JSON to stdout.
def main() -> int:
    args = build_parser().parse_args()
    raw = Path(args.input).read_text(encoding="utf-8")
    payload = json.loads(raw)
    decision = decide_from_payload(payload)
    print(json.dumps({"ok": True, "decision": decision.model_dump()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
