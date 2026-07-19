"""Golden set of test cases for evaluating the incident analysis pipeline.

Each case has known-good expected outputs that we score the pipeline against.
"""

GOLDEN_SET: list[dict] = [
    {
        "id": "gs-001",
        "description": "OOM crash in order-service",
        "input_log": (
            "2024-01-15T10:30:01Z ERROR [order-service] java.lang.OutOfMemoryError: Java heap space\n"
            "2024-01-15T10:30:01Z ERROR [order-service] at com.app.OrderProcessor.process(OrderProcessor.java:142)\n"
            "2024-01-15T10:30:02Z WARN  [order-service] GC overhead limit exceeded, heap usage 98%\n"
            "2024-01-15T10:30:03Z ERROR [order-service] Container killed: OOMKilled (exit code 137)\n"
            "2024-01-15T10:30:04Z WARN  [api-gateway] upstream order-service: connection refused\n"
            "2024-01-15T10:30:05Z ERROR [api-gateway] 502 Bad Gateway for POST /orders\n"
        ),
        "expected_category": "memory_leak",
        "expected_severity": "critical",
        "expected_keywords": ["heap", "memory", "restart", "OOM", "limit"],
    },
    {
        "id": "gs-002",
        "description": "Deployment regression in user-service",
        "input_log": (
            "2024-01-15T14:00:01Z INFO  [user-service] Deployment v2.4.1 started\n"
            "2024-01-15T14:00:05Z INFO  [user-service] Application started on port 8080\n"
            "2024-01-15T14:00:10Z ERROR [user-service] NullPointerException in UserController.getProfile\n"
            "2024-01-15T14:00:11Z ERROR [user-service] NullPointerException in UserController.getProfile\n"
            "2024-01-15T14:00:12Z ERROR [user-service] NullPointerException in UserController.getProfile\n"
            "2024-01-15T14:00:15Z WARN  [api-gateway] user-service error rate spike: 34%\n"
            "2024-01-15T14:00:20Z ERROR [api-gateway] 500 Internal Server Error for GET /users/profile\n"
        ),
        "expected_category": "deployment_regression",
        "expected_severity": "critical",
        "expected_keywords": ["rollback", "NullPointer", "deployment", "v2.4.1", "regression"],
    },
    {
        "id": "gs-003",
        "description": "Database connection pool exhaustion",
        "input_log": (
            "2024-01-15T09:00:01Z WARN  [payment-service] Connection pool: 48/50 active connections\n"
            "2024-01-15T09:00:05Z WARN  [payment-service] Connection pool: 50/50 active connections\n"
            "2024-01-15T09:00:10Z ERROR [payment-service] Connection pool exhausted, timeout after 30000ms\n"
            "2024-01-15T09:00:11Z ERROR [payment-service] Failed to acquire connection from pool\n"
            "2024-01-15T09:00:15Z ERROR [payment-service] org.postgresql.util.PSQLException: connection refused\n"
            "2024-01-15T09:00:20Z WARN  [api-gateway] payment-service latency p99: 35000ms\n"
        ),
        "expected_category": "database",
        "expected_severity": "high",
        "expected_keywords": ["pool", "connection", "increase", "timeout", "close"],
    },
    {
        "id": "gs-004",
        "description": "Network partition affecting inventory-service",
        "input_log": (
            "2024-01-15T16:00:01Z ERROR [inventory-service] Connection timed out: 10.0.1.50:5432\n"
            "2024-01-15T16:00:02Z ERROR [inventory-service] No route to host: 10.0.1.50\n"
            "2024-01-15T16:00:05Z WARN  [order-service] inventory-service unreachable, retrying...\n"
            "2024-01-15T16:00:10Z ERROR [order-service] Failed to check inventory: connection timeout\n"
            "2024-01-15T16:00:15Z WARN  [api-gateway] inventory-service: all health checks failing\n"
        ),
        "expected_category": "network",
        "expected_severity": "high",
        "expected_keywords": ["network", "DNS", "connectivity", "route", "timeout"],
    },
    {
        "id": "gs-005",
        "description": "CPU saturation on payment-service",
        "input_log": (
            "2024-01-15T11:00:01Z WARN  [payment-service] CPU usage: 92%\n"
            "2024-01-15T11:00:05Z WARN  [payment-service] CPU usage: 97%\n"
            "2024-01-15T11:00:10Z WARN  [payment-service] Request queue depth: 1500 (threshold: 200)\n"
            "2024-01-15T11:00:15Z ERROR [payment-service] Request timeout after 30s: POST /process-payment\n"
            "2024-01-15T11:00:20Z WARN  [payment-service] Thread pool exhausted, rejecting requests\n"
            "2024-01-15T11:00:25Z ERROR [api-gateway] payment-service: 504 Gateway Timeout\n"
        ),
        "expected_category": "cpu_saturation",
        "expected_severity": "high",
        "expected_keywords": ["CPU", "scale", "autoscal", "rate-limit", "queue"],
    },
    {
        "id": "gs-006",
        "description": "SSL certificate expired",
        "input_log": (
            "2024-01-15T00:00:01Z ERROR [ingress-nginx] SSL certificate expired for api.example.com\n"
            "2024-01-15T00:00:02Z ERROR [ingress-nginx] SSL_ERROR_EXPIRED_CERT_ALERT\n"
            "2024-01-15T00:00:05Z WARN  [ingress-nginx] TLS handshake failed: certificate has expired\n"
            "2024-01-15T00:00:10Z ERROR [ingress-nginx] 502 Bad Gateway: upstream SSL error\n"
        ),
        "expected_category": "certificate",
        "expected_severity": "critical",
        "expected_keywords": ["certificate", "renew", "SSL", "TLS", "cert-manager"],
    },
    {
        "id": "gs-007",
        "description": "Kafka consumer lag buildup",
        "input_log": (
            "2024-01-15T12:00:01Z WARN  [order-processor] Consumer lag: 500000 messages on topic orders\n"
            "2024-01-15T12:00:10Z WARN  [order-processor] Consumer lag: 750000 messages on topic orders\n"
            "2024-01-15T12:00:20Z ERROR [order-processor] Consumer rebalance failed: timeout\n"
            "2024-01-15T12:00:30Z WARN  [order-processor] Consumer lag: 1200000 messages on topic orders\n"
            "2024-01-15T12:00:40Z ERROR [order-processor] Processing delay: 45 minutes behind real-time\n"
        ),
        "expected_category": "messaging",
        "expected_severity": "high",
        "expected_keywords": ["consumer", "lag", "partition", "scale", "throughput"],
    },
    {
        "id": "gs-008",
        "description": "Container CrashLoopBackOff",
        "input_log": (
            "2024-01-15T08:00:01Z ERROR [auth-service] Error: Cannot find module './config/auth.json'\n"
            "2024-01-15T08:00:01Z FATAL [auth-service] Process exiting with code 1\n"
            "2024-01-15T08:00:05Z WARN  [kubelet] Back-off restarting failed container auth-service\n"
            "2024-01-15T08:00:10Z WARN  [kubelet] Container auth-service: CrashLoopBackOff (restart #4)\n"
            "2024-01-15T08:00:15Z ERROR [api-gateway] auth-service: connection refused on port 3000\n"
        ),
        "expected_category": "container_crash",
        "expected_severity": "critical",
        "expected_keywords": ["config", "CrashLoop", "restart", "module", "mount"],
    },
    {
        "id": "gs-009",
        "description": "Disk space exhaustion",
        "input_log": (
            "2024-01-15T06:00:01Z WARN  [node-agent] Disk usage on /var/lib/docker: 89%\n"
            "2024-01-15T06:00:10Z WARN  [node-agent] Disk usage on /var/lib/docker: 93%\n"
            "2024-01-15T06:00:20Z ERROR [kubelet] Evicting pod: DiskPressure\n"
            "2024-01-15T06:00:25Z ERROR [containerd] failed to pull image: no space left on device\n"
            "2024-01-15T06:00:30Z ERROR [kubelet] Node condition: DiskPressure=True\n"
        ),
        "expected_category": "disk",
        "expected_severity": "high",
        "expected_keywords": ["disk", "clean", "prune", "space", "evict"],
    },
    {
        "id": "gs-010",
        "description": "API rate limiting by third-party provider",
        "input_log": (
            "2024-01-15T15:00:01Z WARN  [payment-service] Stripe API: 429 Too Many Requests\n"
            "2024-01-15T15:00:02Z WARN  [payment-service] X-RateLimit-Remaining: 0, Retry-After: 60\n"
            "2024-01-15T15:00:05Z ERROR [payment-service] Payment processing failed: rate limited\n"
            "2024-01-15T15:00:10Z WARN  [payment-service] Payment queue depth: 340 pending\n"
            "2024-01-15T15:00:15Z ERROR [payment-service] 12 payments failed in last 60 seconds\n"
        ),
        "expected_category": "rate_limit",
        "expected_severity": "medium",
        "expected_keywords": ["backoff", "rate", "limit", "cache", "retry"],
    },
    {
        "id": "gs-011",
        "description": "DNS resolution failures",
        "input_log": (
            "2024-01-15T13:00:01Z ERROR [inventory-service] DNS resolution failed for db.internal.svc\n"
            "2024-01-15T13:00:02Z ERROR [order-service] DNS lookup timed out: redis.internal.svc\n"
            "2024-01-15T13:00:05Z WARN  [payment-service] nslookup: NXDOMAIN for config-svc.default.svc.cluster.local\n"
            "2024-01-15T13:00:10Z ERROR [kubelet] CoreDNS pods not ready in kube-system namespace\n"
        ),
        "expected_category": "dns",
        "expected_severity": "high",
        "expected_keywords": ["DNS", "CoreDNS", "resolve", "nslookup"],
    },
    {
        "id": "gs-012",
        "description": "Upstream timeout cascade",
        "input_log": (
            "2024-01-15T17:00:01Z WARN  [api-gateway] upstream inventory-service latency p99: 28000ms\n"
            "2024-01-15T17:00:05Z ERROR [api-gateway] 504 Gateway Timeout for GET /inventory/check\n"
            "2024-01-15T17:00:06Z WARN  [api-gateway] Retry 1/3 to inventory-service\n"
            "2024-01-15T17:00:36Z WARN  [api-gateway] Retry 2/3 to inventory-service\n"
            "2024-01-15T17:01:06Z ERROR [api-gateway] All retries exhausted for inventory-service\n"
            "2024-01-15T17:01:07Z WARN  [order-service] Cascade: order creation failed due to inventory check timeout\n"
        ),
        "expected_category": "timeout",
        "expected_severity": "high",
        "expected_keywords": ["timeout", "circuit", "breaker", "retry", "latency"],
    },
]
