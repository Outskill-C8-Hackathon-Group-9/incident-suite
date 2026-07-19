import { useState } from "react";
import { analyze } from "./api.ts";
import type { TraceEntry, AnalysisResult, NodeStateMap } from "./types";

import AppHeader      from "./components/AppHeader.tsx";
import LeftPanel      from "./components/LeftPanel.tsx";
import TerminalWindow from "./components/TerminalWindow.tsx";
import Results        from "./components/Results.tsx";
import RightPanel     from "./components/RightPanel.tsx";

// ─── Original logical constants (unchanged) ──────────────────────────────────
const NODES = ["classifier", "rag", "remediation", "cookbook", "jira", "notifier"] as const;

export default function App() {
  // ─── Original state (unchanged logic) ────────────────────────────────────
  const [file, setFile]       = useState<File | null>(null);
  const [active, setActive]   = useState<NodeStateMap>({});
  const [trace, setTrace]     = useState<TraceEntry[]>([]);
  const [result, setResult]   = useState<AnalysisResult | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [error, setError]     = useState<string | null>(null);

  // ─── Original run logic (unchanged) ──────────────────────────────────────
  const run = async (): Promise<void> => {
    if (!file) return;
    setRunning(true);
    setActive({});
    setTrace([]);
    setResult(null);
    setError(null);
    await analyze(file, {
      onNode: ({ node, update }) => {
        setActive((a) => ({ ...a, [node]: true }));
        if (update?.trace) setTrace((t) => [...t, ...(update.trace ?? [])]);
      },
      onDone: (finalState) => {
        setResult(finalState);
        setRunning(false);
      },
      onError: (err) => {
        setError(err.message);
        setRunning(false);
      },
    });
  };

  // ─── Derive "done" map once results arrive ────────────────────────────────
  const done: NodeStateMap = result
    ? NODES.reduce<NodeStateMap>((acc, n) => ({ ...acc, [n]: !!active[n] }), {})
    : {};

  // ─── Count critical issues for the header badge ───────────────────────────
  const criticalCount =
    result?.issues?.filter((i) => i.severity?.toLowerCase() === "critical").length ?? 0;

  // ─── 3-column dashboard layout ────────────────────────────────────────────
  return (
    <div className="dashboard-grid">
      {/* Row 1 — Header */}
      <AppHeader running={running} criticalCount={criticalCount} />

      {/* Row 2 Col 1 — Left sidebar */}
      <LeftPanel
        file={file}
        setFile={setFile}
        running={running}
        onRun={() => { void run(); }}
        active={active}
        done={done}
      />

      {/* Row 2 Col 2 — Center: terminal + results */}
      <main className="center-panel">
        {error && (
          <div className="error-banner" role="alert">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            {error}
          </div>
        )}

        <TerminalWindow
          trace={trace}
          fileName={file?.name}
          running={running}
        />

        {result && <Results state={result} />}

        {!result && !running && !error && (
          <div className="empty-state">
            <p>Upload a log file and click <strong>Run Live Analysis</strong> to begin</p>
          </div>
        )}
      </main>

      {/* Row 2 Col 3 — Right panel */}
      <RightPanel state={result} running={running} />

      {/* Row 3 — Status bar */}
      <footer className="status-bar">
        <div className="status-item">
          <span className="status-dot-green" />
          <span>API GATEWAY: ONLINE</span>
        </div>
        <div className="status-item">
          LATENCY: <span style={{ color: "var(--agent-done)", marginLeft: 4 }}>42ms</span>
        </div>
        <div className="status-item">
          <span>Clear Log</span>
        </div>
        <div className="status-item">
          <span className="status-kbd">⌘K</span>
          <span>Search Agent Docs</span>
        </div>
        <div className="status-bar-right">
          {running && (
            <div className="status-item" style={{ color: "var(--accent-bright)" }}>
              <div className="spinner" style={{ width: 8, height: 8, marginRight: 4 }} />
              Analysis in progress…
            </div>
          )}
          {result && (
            <div className="status-item" style={{ color: "var(--agent-done)" }}>
              ✓ Analysis complete
            </div>
          )}
        </div>
      </footer>
    </div>
  );
}
