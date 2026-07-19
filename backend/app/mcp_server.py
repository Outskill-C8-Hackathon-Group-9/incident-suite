"""MCP (Model Context Protocol) server for the Incident Analysis Suite.

Exposes the incident analysis pipeline as MCP tools so that any
MCP-compatible client (Cursor, Claude Desktop, etc.) can plug in
and use this service directly.

Run standalone:  python -m app.mcp_server
"""

import json
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def create_mcp_server():
    """Create and configure the MCP server with all available tools."""
    try:
        from mcp.server import Server
        from mcp.types import Tool, TextContent
        from mcp.server.stdio import run_server
    except ImportError:
        logger.error(
            "MCP SDK not installed. Install with: pip install mcp"
        )
        return None

    server = Server("incident-analysis-suite")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="analyze_logs",
                description=(
                    "Analyze operational logs for incidents. Detects issues, "
                    "classifies severity, retrieves matching runbooks via RAG, "
                    "proposes remediations, and builds an incident response checklist."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "logs": {
                            "type": "string",
                            "description": "Raw log text to analyze",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional filename for context",
                            "default": "mcp-input.log",
                        },
                    },
                    "required": ["logs"],
                },
            ),
            Tool(
                name="analyze_image",
                description=(
                    "Analyze a screenshot from a monitoring tool (Grafana, "
                    "Datadog, terminal, etc.) and provide incident resolution."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "image_base64": {
                            "type": "string",
                            "description": "Base64-encoded image data",
                        },
                        "description": {
                            "type": "string",
                            "description": "Text description of what the image shows",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="run_evals",
                description=(
                    "Run the evaluation suite against the golden set of test "
                    "cases. Returns accuracy metrics for classification, severity, "
                    "and retrieval quality."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "use_reranking": {
                            "type": "boolean",
                            "description": "Whether to use cross-encoder reranking",
                            "default": True,
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="search_knowledge",
                description=(
                    "Search the incident knowledge base for runbooks matching "
                    "a query. Uses RAG retrieval with optional reranking."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (e.g. 'OOM crash java')",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="add_runbook",
                description=(
                    "Add a new runbook entry to the knowledge base. The entry "
                    "will be embedded and available for future RAG retrieval."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Runbook title",
                        },
                        "category": {
                            "type": "string",
                            "description": "Issue category (e.g. 'database', 'network')",
                        },
                        "content": {
                            "type": "string",
                            "description": "Runbook content with symptoms and resolution steps",
                        },
                    },
                    "required": ["title", "category", "content"],
                },
            ),
            Tool(
                name="get_severity_breakdown",
                description=(
                    "Analyze logs and return a detailed severity classification "
                    "with confidence scores, blast radius, and escalation guidance."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "logs": {
                            "type": "string",
                            "description": "Raw log text to classify",
                        },
                    },
                    "required": ["logs"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            result = await _dispatch_tool(name, arguments)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str),
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}),
            )]

    return server


async def _dispatch_tool(name: str, arguments: dict) -> dict:
    """Route tool calls to the appropriate handler."""
    if name == "analyze_logs":
        return await _tool_analyze_logs(arguments)
    elif name == "analyze_image":
        return await _tool_analyze_image(arguments)
    elif name == "run_evals":
        return await _tool_run_evals(arguments)
    elif name == "search_knowledge":
        return await _tool_search_knowledge(arguments)
    elif name == "add_runbook":
        return await _tool_add_runbook(arguments)
    elif name == "get_severity_breakdown":
        return await _tool_severity_breakdown(arguments)
    else:
        return {"error": f"Unknown tool: {name}"}


async def _tool_analyze_logs(args: dict) -> dict:
    from app.graph import graph

    logs = args["logs"]
    filename = args.get("filename", "mcp-input.log")
    initial = {"raw_logs": logs, "filename": filename, "trace": []}
    config = {"configurable": {"thread_id": f"mcp-{id(logs)}"}}

    final = dict(initial)
    async for chunk in graph.astream(initial, config, stream_mode="updates"):
        for _node, update in chunk.items():
            if isinstance(update, dict):
                for key, value in update.items():
                    if key == "trace":
                        final.setdefault("trace", []).extend(value or [])
                    else:
                        final[key] = value

    return {
        "issues": final.get("issues", []),
        "remediations": final.get("remediations", []),
        "cookbook": final.get("cookbook"),
        "fallback_results": final.get("fallback_results"),
    }


async def _tool_analyze_image(args: dict) -> dict:
    from app.nodes.image_analyzer import analyze_image_with_vision

    analysis = analyze_image_with_vision(
        image_base64=args.get("image_base64"),
        description=args.get("description", ""),
    )
    return analysis.model_dump()


async def _tool_run_evals(args: dict) -> dict:
    from app.evals.evaluator import run_eval_suite

    use_reranking = args.get("use_reranking", True)
    results, summary = run_eval_suite(use_reranking=use_reranking)
    return {
        "summary": summary.model_dump(),
        "results": [r.model_dump() for r in results],
    }


async def _tool_search_knowledge(args: dict) -> dict:
    from app.knowledge.runbook_store import retrieve

    query = args["query"]
    top_k = args.get("top_k", 5)
    docs = retrieve(query, k=top_k)
    return {
        "query": query,
        "results": [
            {
                "title": d.metadata.get("title", "unknown"),
                "category": d.metadata.get("category", "unknown"),
                "content": d.page_content,
                "source": d.metadata.get("source", "seed"),
            }
            for d in docs
        ],
    }


async def _tool_add_runbook(args: dict) -> dict:
    from app.knowledge.hf_datasets import add_new_issue_to_store

    added = add_new_issue_to_store(
        title=args["title"],
        category=args["category"],
        content=args["content"],
        source="mcp-manual",
    )
    return {
        "added": added,
        "title": args["title"],
        "message": "Runbook added to knowledge base." if added else "Runbook already exists.",
    }


async def _tool_severity_breakdown(args: dict) -> dict:
    from app.parsing import parse_logs, cluster_errors
    from app.models import ClassifierOutput
    from app.llm import get_llm
    from app.nodes.classifier import CLASSIFY_PROMPT

    entries = parse_logs(args["logs"])
    clusters = cluster_errors(entries)
    if not clusters:
        return {"issues": [], "message": "No error clusters found."}

    clusters_text = "\n\n".join(
        f"[{c.count}x] level={c.level} service={c.example_service} sig={c.signature}\n"
        + "\n".join(f"  {ln}" for ln in c.sample_lines)
        for c in clusters
    )

    llm = get_llm().with_structured_output(ClassifierOutput, method="function_calling")
    result = llm.invoke(CLASSIFY_PROMPT.format(clusters=clusters_text))

    return {
        "issues": [i.model_dump() for i in result.issues],
        "severity_summary": {
            sev: sum(1 for i in result.issues if i.severity == sev)
            for sev in ("critical", "high", "medium", "low", "info")
            if any(i.severity == sev for i in result.issues)
        },
    }


async def main():
    """Run the MCP server via stdio transport."""
    from app.knowledge.runbook_store import seed_if_empty
    from app.knowledge.hf_datasets import ingest_hf_knowledge_to_store

    seed_if_empty()
    ingest_hf_knowledge_to_store()

    server = create_mcp_server()
    if server is None:
        print("ERROR: MCP SDK not available. Install with: pip install mcp")
        return

    from mcp.server.stdio import run_server
    await run_server(server)


if __name__ == "__main__":
    asyncio.run(main())
