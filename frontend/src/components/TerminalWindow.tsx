import { useEffect, useRef } from "react";
import type { TraceEntry } from "../types";

interface LogLineProps {
  text: string;
  node: string | null;
}

interface TerminalWindowProps {
  trace: TraceEntry[];
  fileName: string | undefined;
  running: boolean;
}

type LogLevel = "INFO" | "WARN" | "WARNING" | "ERROR" | "FATAL" | "CRITICAL";

const SEVERITY_RE = /\b(INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b/;

/** Renders a single trace/log line with severity-coloured keywords */
function LogLine({ text, node }: LogLineProps) {
  const severityMatch = text.match(SEVERITY_RE);
  const isSystem = node !== null;

  if (isSystem && !severityMatch) {
    return (
      <div className="log-line log-line-system">
        <span className="log-level log-system">[{node}]</span>
        <span className="log-msg">{text}</span>
      </div>
    );
  }

  if (severityMatch) {
    const level = severityMatch[1] as LogLevel;
    const cls = `log-${level.toLowerCase()}`;
    const [before, ...after] = text.split(severityMatch[0]);
    return (
      <div className="log-line">
        {before && <span className="log-time">{before}</span>}
        <span className={`log-level ${cls}`}>{level}</span>
        <span className="log-msg">{after.join(level)}</span>
      </div>
    );
  }

  return (
    <div className="log-line">
      <span className="log-msg">{text}</span>
    </div>
  );
}

export default function TerminalWindow({ trace, fileName, running }: TerminalWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [trace]);

  const displayName = fileName ?? "ops-logs.log";

  return (
    <div className="terminal-window">
      {/* macOS titlebar */}
      <div className="terminal-titlebar">
        <div className="terminal-dots">
          <div className="terminal-dot red" />
          <div className="terminal-dot yellow" />
          <div className="terminal-dot green" />
        </div>
        <span className="terminal-filename">{displayName}</span>
        <div className="terminal-actions">
          <button className="terminal-action-btn" title="Search logs" aria-label="Search">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
          <button className="terminal-action-btn" title="Download logs" aria-label="Download">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7,10 12,15 17,10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          </button>
        </div>
      </div>

      {/* Log body */}
      <div className="terminal-body">
        {trace.length === 0 ? (
          <div className="terminal-empty">
            <span>Waiting for log stream</span>
            <span className="terminal-cursor" />
          </div>
        ) : (
          trace.map((entry, i) => (
            <LogLine key={i} text={entry.message} node={entry.node} />
          ))
        )}
        {running && trace.length > 0 && (
          <div className="log-line">
            <span className="log-level log-system">[System]</span>
            <span className="log-msg">
              AI Agent analyzing trace… <span className="terminal-cursor" />
            </span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
