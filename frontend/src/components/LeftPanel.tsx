import { useRef, useState } from "react";
import type { AgentId, AgentMeta, NodeStateMap } from "../types";

interface AgentRowProps {
  agent: AgentMeta;
  active: boolean;
  done: boolean;
}

interface LeftPanelProps {
  file: File | null;
  setFile: (file: File) => void;
  apiKey: string;
  setApiKey: (key: string) => void;
  running: boolean;
  onRun: () => void;
  active: NodeStateMap;
  done: NodeStateMap;
}

const AGENTS: AgentMeta[] = [
  { id: "classifier",  label: "Log Classifier",  icon: "🔍" },
  { id: "remediation", label: "Remediator",       icon: "🛡️" },
  { id: "cookbook",    label: "Cookbook Builder", icon: "📋" },
  { id: "notifier",    label: "Slack Notifier",   icon: "💬" },
  { id: "jira",        label: "Jira Integrator",  icon: "🎫" },
];

type AgentState = "idle" | "active" | "done";

function AgentRow({ agent, active, done }: AgentRowProps) {
  const isActive = !done && active;
  const isDone = done;
  const state: AgentState = isDone ? "done" : isActive ? "active" : "idle";

  const statusLabel = isDone ? "Done" : isActive ? "Running…" : "Waiting";
  const progressWidth = isDone ? "100%" : isActive ? "55%" : "0%";

  return (
    <div className={`agent-row is-${state}`}>
      <div className="agent-row-top">
        <div className="agent-icon">{agent.icon}</div>
        <span className="agent-name">{agent.label}</span>
        <span className={`agent-status ${state}`}>{statusLabel}</span>
      </div>
      <div className="agent-progress-track">
        <div
          className={`agent-progress-fill ${state}`}
          style={{ width: progressWidth }}
        />
      </div>
    </div>
  );
}

export default function LeftPanel({
  file,
  setFile,
  apiKey,
  setApiKey,
  running,
  onRun,
  active,
  done,
}: LeftPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState<boolean>(false);
  const [keyVisible, setKeyVisible] = useState<boolean>(false);

  const keyValid = apiKey.trim().length >= 10;

  const handleFile = (f: File | null | undefined): void => {
    if (!f) return;
    setFile(f);
  };

  const anyActive = AGENTS.some(
    (a: AgentMeta) => active[a.id as AgentId] && !done[a.id as AgentId],
  );

  return (
    <aside className="left-panel">
      {/* API KEY INPUT */}
      <section>
        <p className="panel-section-title">OpenRouter API Key</p>
        <div className={`api-key-field ${keyValid ? "is-valid" : apiKey.length > 0 ? "is-invalid" : ""}`}>
          <svg className="api-key-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <input
            id="openrouter-api-key"
            className="api-key-input"
            type={keyVisible ? "text" : "password"}
            placeholder="sk-or-v1-…"
            value={apiKey}
            disabled={running}
            onChange={(e) => setApiKey(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            className="api-key-toggle"
            onClick={() => setKeyVisible((v) => !v)}
            title={keyVisible ? "Hide key" : "Show key"}
            aria-label={keyVisible ? "Hide API key" : "Show API key"}
          >
            {keyVisible ? (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        </div>
        {apiKey.length > 0 && !keyValid && (
          <p className="api-key-hint api-key-hint--error">Key looks too short — please check it</p>
        )}
        {keyValid && (
          <p className="api-key-hint api-key-hint--ok">✓ Key accepted</p>
        )}
      </section>

      <div className="agents-divider" />

      {/* INPUT LOGS */}
      <section>
        <p className="panel-section-title">Input Logs</p>

        <div
          className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""} ${running ? "disabled" : ""}`}
          onClick={() => !running && inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!running) handleFile(e.dataTransfer.files[0]);
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".log,.txt,.json"
            style={{ display: "none" }}
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <div className="dropzone-icon">
            {file ? (
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14,2 14,8 20,8" />
                <polyline points="9,15 12,18 15,15" />
                <line x1="12" y1="12" x2="12" y2="18" />
              </svg>
            ) : (
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <polyline points="16,16 12,12 8,16" />
                <line x1="12" y1="12" x2="12" y2="21" />
                <path d="M20.39,18.39A5,5,0,0,0,18,9h-1.26A8,8,0,1,0,3,16.3" />
              </svg>
            )}
          </div>
          <p className="dropzone-label">
            {file ? file.name : "Drop log files here"}
          </p>
          <p className="dropzone-hint">
            {file ? `${(file.size / 1024).toFixed(1)} KB` : ".log .json .txt (Max 50MB)"}
          </p>
        </div>

        <button
          id="run-analysis-btn"
          className="btn-primary"
          onClick={onRun}
          disabled={!file || !keyValid || running}
        >
          {running ? (
            <>
              <div className="spinner" />
              Analyzing…
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5,3 19,12 5,21" />
              </svg>
              Run Live Analysis
            </>
          )}
        </button>
      </section>

      <div className="agents-divider" />

      {/* AGENT SWARM */}
      <section>
        <div className="agent-swarm-header">
          <p className="panel-section-title" style={{ marginBottom: 0 }}>Agent Swarm</p>
          <div className="agent-swarm-status">
            <span className={`status-dot ${anyActive ? "active" : ""}`} />
            {anyActive ? "ACTIVE" : running ? "RUNNING" : "IDLE"}
          </div>
        </div>

        <div className="agents-list" style={{ marginTop: "var(--space-3)" }}>
          {AGENTS.map((a) => (
            <AgentRow
              key={a.id}
              agent={a}
              active={!!active[a.id]}
              done={!!done[a.id]}
            />
          ))}
        </div>
      </section>
    </aside>
  );
}
