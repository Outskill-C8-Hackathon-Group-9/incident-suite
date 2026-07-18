import re
from collections import defaultdict
from app.models import LogEntry, ErrorCluster

_TS = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?Z?)")
_LEVEL = re.compile(r"\b(ERROR|ERR|FATAL|CRITICAL|WARN(?:ING)?|INFO|DEBUG|TRACE)\b", re.I)
_SERVICE = re.compile(r"[\[\s](?:svc=)?([a-z0-9]+-service|[a-z0-9]+-svc|api-gateway)[\]\s:]", re.I)

_ERROR_LEVELS = ("ERROR", "ERR", "FATAL", "CRITICAL", "WARN", "WARNING")


def parse_logs(raw: str) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for i, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        ts = _TS.search(line)
        lvl = _LEVEL.search(line)
        svc = _SERVICE.search(line)
        entries.append(LogEntry(
            line_no=i,
            timestamp=ts.group(1) if ts else None,
            level=lvl.group(1).upper() if lvl else None,
            service=svc.group(1).lower() if svc else None,
            message=line.strip(),
            raw=line,
        ))
    return entries


def _signature(msg: str) -> str:
    s = re.sub(r"[0-9a-fA-F]{8,}", "<hex>", msg)
    s = re.sub(r"\b\d+\b", "<n>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:160]


def cluster_errors(entries: list[LogEntry]) -> list[ErrorCluster]:
    buckets: dict[str, list[LogEntry]] = defaultdict(list)
    for e in entries:
        if e.level and e.level.upper() in _ERROR_LEVELS:
            buckets[_signature(e.message)].append(e)

    clusters: list[ErrorCluster] = []
    for sig, es in sorted(buckets.items(), key=lambda kv: len(kv[1]), reverse=True):
        clusters.append(ErrorCluster(
            signature=sig,
            count=len(es),
            level=es[0].level or "ERROR",
            example_service=next((e.service for e in es if e.service), None),
            sample_lines=[e.raw for e in es[:3]],
            line_numbers=[e.line_no for e in es[:20]],
        ))
    return clusters[:25]