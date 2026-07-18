"""Curated runbook / past-incident corpus. This is the RAG source data.

Each entry is a short, self-contained runbook the remediation agent can ground its
fixes in. Add more entries to improve retrieval quality — this is your knowledge base,
NOT user-uploaded logs.
"""

RUNBOOKS: list[dict] = [
    {
        "title": "OOM / memory leak in a JVM service",
        "category": "memory_leak",
        "service_hint": "order-service",
        "content": (
            "Symptoms: steadily rising heap usage, long GC pauses, java.lang.OutOfMemoryError, "
            "container OOMKilled and restart loops. Downstream services see connection refused as "
            "the pod restarts. Resolution: (1) restart/scale the affected pod to restore service; "
            "(2) capture a heap dump before restart if possible; (3) raise the memory limit as a "
            "temporary mitigation; (4) identify the leak (unbounded caches, thread/connection leaks) "
            "and ship a fix; (5) add a heap-usage alert at 80%. Rollback the last release if the leak "
            "started right after a deploy."
        ),
    },
    {
        "title": "Bad deployment causing NullPointerException regression",
        "category": "deployment_regression",
        "service_hint": "user-service",
        "content": (
            "Symptoms: a spike of NullPointerException (or 5xx) immediately after a new version is "
            "deployed; upstream gateways report elevated latency and 502s. Resolution: (1) roll back "
            "to the previous known-good version with 'kubectl rollout undo deployment/<service>'; "
            "(2) confirm error rate returns to baseline; (3) reproduce in staging; (4) add a "
            "regression test for the null path; (5) re-deploy behind a canary. Fast rollback beats "
            "hotfixing under pressure."
        ),
    },
    {
        "title": "Database connection pool exhaustion",
        "category": "database",
        "service_hint": "database-proxy",
        "content": (
            "Symptoms: 'connection pool exhausted' / 'timeout acquiring connection' errors, rising "
            "query latency, cascading timeouts in dependent services. Resolution: (1) increase pool "
            "size as an immediate mitigation; (2) find and kill long-running or leaked connections; "
            "(3) ensure connections are released (check for missing close/finally); (4) add a "
            "connection-wait-time alert; (5) consider a read replica if read-heavy."
        ),
    },
    {
        "title": "Network partition isolating a service",
        "category": "network",
        "service_hint": "inventory-service",
        "content": (
            "Symptoms: sudden 'connection timed out' / 'no route to host' between specific services "
            "while others are healthy; one service becomes unreachable cluster-wide. Resolution: "
            "(1) check network policies, security groups, and CNI health; (2) verify DNS resolution; "
            "(3) restart the affected node/pod networking if degraded; (4) fail over to a healthy "
            "replica/zone; (5) add synthetic connectivity checks between critical service pairs."
        ),
    },
    {
        "title": "CPU saturation and request queue buildup",
        "category": "cpu_saturation",
        "service_hint": "payment-service",
        "content": (
            "Symptoms: CPU pinned near 100%, growing request queue, rising p99 latency and timeouts. "
            "Resolution: (1) scale out horizontally to add capacity; (2) shed or rate-limit "
            "non-critical traffic; (3) profile hot paths for a fix; (4) enable autoscaling on CPU; "
            "(5) verify no infinite/retry storm is amplifying load."
        ),
    },
    {
        "title": "Upstream timeout / latency cascade",
        "category": "timeout",
        "service_hint": "api-gateway",
        "content": (
            "Symptoms: gateway reports upstream latency spikes and 504/502; retries amplify load. "
            "Resolution: (1) identify the slow upstream from traces; (2) apply circuit breakers and "
            "sane timeouts; (3) reduce retry aggressiveness; (4) scale or roll back the slow upstream; "
            "(5) add p99 latency alerts per upstream."
        ),
    },
]