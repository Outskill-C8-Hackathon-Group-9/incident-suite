"""Hugging Face datasets integration for incident resolution knowledge.

Loads curated DevOps/SRE-related datasets from Hugging Face and ingests them
into the Chroma vector store so the RAG pipeline can retrieve them as
supplementary runbooks when the local corpus has no match.
"""

import logging
from typing import Optional

from langchain_core.documents import Document

from app.knowledge.runbook_store import get_store, add_documents_chunked

logger = logging.getLogger(__name__)

HF_INCIDENT_DATASETS = [
    {
        "repo": "bigcode/the-stack-smol",
        "subset": "data/yaml",
        "description": "Infrastructure config snippets for error pattern matching",
    },
    {
        "repo": "nvidia/ChatQA-Training-Data",
        "subset": None,
        "description": "QA pairs useful for incident troubleshooting knowledge",
    },
]

_INCIDENT_KNOWLEDGE: list[dict] = [
    {
        "title": "Kubernetes CrashLoopBackOff resolution",
        "category": "container_crash",
        "content": (
            "Symptoms: pod repeatedly restarts, status shows CrashLoopBackOff, "
            "exponential backoff delay between restarts. "
            "Resolution: (1) check logs with kubectl logs <pod> --previous; "
            "(2) verify resource limits are not too low; "
            "(3) check liveness/readiness probe configuration; "
            "(4) verify image tag and pull secrets; "
            "(5) check for missing env vars or config maps; "
            "(6) review init container failures."
        ),
    },
    {
        "title": "SSL/TLS certificate expiry causing 502 errors",
        "category": "certificate",
        "content": (
            "Symptoms: sudden 502 Bad Gateway, SSL handshake failures, "
            "certificate expired warnings in logs. "
            "Resolution: (1) check cert expiry with openssl s_client -connect host:443; "
            "(2) renew certificate via cert-manager or manual process; "
            "(3) restart ingress controller after renewal; "
            "(4) set up cert expiry monitoring with 30-day alerts; "
            "(5) consider using Let's Encrypt with auto-renewal."
        ),
    },
    {
        "title": "Disk space exhaustion on nodes",
        "category": "disk",
        "content": (
            "Symptoms: pods evicted, node NotReady, 'no space left on device' errors, "
            "image pulls failing. "
            "Resolution: (1) identify large files with du -sh /*; "
            "(2) clean Docker images: docker system prune -a; "
            "(3) clear old logs: journalctl --vacuum-size=500M; "
            "(4) expand PVCs or add storage; "
            "(5) set log rotation and image garbage collection policies."
        ),
    },
    {
        "title": "DNS resolution failures in cluster",
        "category": "dns",
        "content": (
            "Symptoms: service discovery fails, nslookup times out inside pods, "
            "connection errors to service names but IP access works. "
            "Resolution: (1) check CoreDNS pods: kubectl -n kube-system get pods; "
            "(2) verify DNS policy in pod spec; "
            "(3) check /etc/resolv.conf inside affected pod; "
            "(4) restart CoreDNS if stuck; "
            "(5) check network policies blocking UDP port 53."
        ),
    },
    {
        "title": "Redis connection pool saturation",
        "category": "cache",
        "content": (
            "Symptoms: 'max number of clients reached' errors, increasing latency "
            "on cache reads, connection timeout errors. "
            "Resolution: (1) increase maxclients in redis.conf; "
            "(2) check for connection leaks in application code; "
            "(3) implement connection pooling with proper max-idle settings; "
            "(4) add Redis connection monitoring; "
            "(5) consider Redis Cluster for horizontal scaling."
        ),
    },
    {
        "title": "Kafka consumer lag buildup",
        "category": "messaging",
        "content": (
            "Symptoms: consumer group lag steadily increasing, processing delays, "
            "messages piling up in partitions. "
            "Resolution: (1) check consumer health and rebalancing; "
            "(2) increase consumer instances or partitions; "
            "(3) optimize message processing (batch, async); "
            "(4) check for slow downstream dependencies; "
            "(5) temporarily increase consumer fetch size; "
            "(6) monitor with kafka-consumer-groups.sh --describe."
        ),
    },
    {
        "title": "Elasticsearch cluster yellow/red status",
        "category": "search",
        "content": (
            "Symptoms: unassigned shards, search timeouts, indexing rejections, "
            "cluster health yellow or red. "
            "Resolution: (1) check unassigned shards: GET _cluster/allocation/explain; "
            "(2) verify disk watermarks not breached; "
            "(3) rebalance: POST _cluster/reroute; "
            "(4) add data nodes if capacity issue; "
            "(5) reduce replica count temporarily for red index; "
            "(6) check JVM heap usage on nodes."
        ),
    },
    {
        "title": "API rate limiting and throttling errors",
        "category": "rate_limit",
        "content": (
            "Symptoms: HTTP 429 Too Many Requests, x-ratelimit-remaining: 0 headers, "
            "sudden spike in request rejections. "
            "Resolution: (1) implement exponential backoff with jitter; "
            "(2) add request caching layer; "
            "(3) review and optimize API call patterns; "
            "(4) request rate limit increase if legitimate; "
            "(5) implement circuit breaker pattern; "
            "(6) distribute requests across multiple API keys if allowed."
        ),
    },
    {
        "title": "Container image pull failures (ImagePullBackOff)",
        "category": "container_image",
        "content": (
            "Symptoms: pods stuck in ImagePullBackOff, 'repository not found' or "
            "'unauthorized' in events. "
            "Resolution: (1) verify image tag exists in registry; "
            "(2) check imagePullSecrets in pod spec; "
            "(3) verify registry credentials: kubectl get secret; "
            "(4) check network connectivity to registry; "
            "(5) try pulling image manually on the node; "
            "(6) check registry rate limits (Docker Hub: 100 pulls/6h)."
        ),
    },
    {
        "title": "Deadlock detection in database transactions",
        "category": "database",
        "content": (
            "Symptoms: queries hanging indefinitely, 'deadlock detected' errors, "
            "transaction timeouts, connection pool growing. "
            "Resolution: (1) identify deadlock participants: SHOW ENGINE INNODB STATUS; "
            "(2) review transaction ordering across services; "
            "(3) add lock timeout: SET innodb_lock_wait_timeout=5; "
            "(4) reduce transaction scope and duration; "
            "(5) use SELECT ... FOR UPDATE SKIP LOCKED where possible; "
            "(6) add deadlock retry logic in application."
        ),
    },
    {
        "title": "Prometheus/Grafana alerting pipeline failure",
        "category": "monitoring",
        "content": (
            "Symptoms: alerts not firing, Alertmanager unreachable, stale metrics, "
            "scrape errors in Prometheus targets. "
            "Resolution: (1) check Alertmanager status and logs; "
            "(2) verify alert rules: promtool check rules; "
            "(3) test notification channel connectivity; "
            "(4) check Prometheus scrape targets health; "
            "(5) verify service discovery configuration; "
            "(6) restart Alertmanager if config changes not applied."
        ),
    },
    {
        "title": "Load balancer health check failures",
        "category": "load_balancer",
        "content": (
            "Symptoms: instances removed from target group, intermittent 503 errors, "
            "unhealthy targets in LB dashboard. "
            "Resolution: (1) verify health check endpoint returns 200; "
            "(2) check health check path, port, and protocol match; "
            "(3) increase health check timeout if app startup is slow; "
            "(4) verify security groups allow health check traffic; "
            "(5) check application logs for health endpoint errors."
        ),
    },
]


def load_hf_dataset_as_documents(
    repo_id: str,
    subset: Optional[str] = None,
    max_docs: int = 50,
    text_field: str = "text",
    split: str = "train",
) -> list[Document]:
    """Load a HF dataset and convert rows to LangChain Documents.

    Falls back gracefully if the dataset is unavailable or the schema
    doesn't match expectations.
    """
    try:
        from datasets import load_dataset

        kwargs: dict = {"split": f"{split}[:{max_docs}]", "trust_remote_code": True}
        if subset:
            ds = load_dataset(repo_id, subset, **kwargs)
        else:
            ds = load_dataset(repo_id, **kwargs)

        docs = []
        for row in ds:
            content = row.get(text_field) or row.get("content") or str(row)
            docs.append(Document(
                page_content=content[:2000],
                metadata={
                    "source": f"hf:{repo_id}",
                    "title": row.get("title", repo_id),
                    "category": "hf_dataset",
                },
            ))
        logger.info("Loaded %d docs from HF dataset %s", len(docs), repo_id)
        return docs
    except Exception as e:
        logger.warning("Failed to load HF dataset %s: %s", repo_id, e)
        return []


def search_hf_for_issue(query: str, top_k: int = 5) -> list[dict]:
    """Search HF Hub for datasets relevant to an incident query.

    Uses the huggingface_hub API to find dataset cards matching the query.
    Returns metadata dicts (id, description, tags).
    """
    try:
        from huggingface_hub import HfApi

        api = HfApi()
        results = list(api.list_datasets(search=query, limit=top_k, sort="likes"))
        return [
            {
                "id": ds.id,
                "description": (ds.description or "")[:300],
                "tags": ds.tags or [],
                "likes": ds.likes,
            }
            for ds in results
        ]
    except Exception as e:
        logger.warning("HF Hub search failed: %s", e)
        return []


def ingest_hf_knowledge_to_store() -> int:
    """Ingest the curated HF incident knowledge into the vector store (chunked).

    Returns the number of chunks added.
    """
    store = get_store()
    existing = store.get()
    existing_titles = set()
    if existing and existing.get("metadatas"):
        for m in existing["metadatas"]:
            if not m:
                continue
            existing_titles.add(m.get("original_title") or m.get("title") or "")

    docs = []
    for kb in _INCIDENT_KNOWLEDGE:
        if kb["title"] in existing_titles:
            continue
        docs.append(Document(
            page_content=kb["content"],
            metadata={
                "title": kb["title"],
                "category": kb["category"],
                "service_hint": "",
                "source": "hf_curated",
                "environment": "production",
                "domain": "devops",
            },
        ))

    if not docs:
        return 0
    n = add_documents_chunked(docs)
    logger.info("Ingested %d HF knowledge chunks from %d docs.", n, len(docs))
    return n


def add_new_issue_to_store(
    title: str, category: str, content: str, source: str = "learned"
) -> bool:
    """Dynamically add a newly learned issue resolution to the vector store.

    Used by the fallback mechanism when a new/unknown issue is encountered
    and a resolution is found via HF dataset search.
    """
    store = get_store()
    existing = store.get()
    existing_titles = set()
    if existing and existing.get("metadatas"):
        for m in existing["metadatas"]:
            if not m:
                continue
            existing_titles.add(m.get("original_title") or m.get("title") or "")

    if title in existing_titles:
        logger.info("Issue '%s' already in store, skipping.", title)
        return False

    doc = Document(
        page_content=content,
        metadata={
            "title": title,
            "category": category,
            "service_hint": "",
            "source": source,
            "environment": "production",
            "domain": "devops",
        },
    )
    add_documents_chunked([doc])
    logger.info("Added new issue '%s' to vector store.", title)
    return True
