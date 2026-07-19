import type { AnalysisResult, NotificationResult, TicketEntry } from "../types";

// ─── Orchestrator Panel ───────────────────────────────────────────────────────

interface OrchestratorPanelProps {
  state: AnalysisResult | null;
  running: boolean;
}

function OrchestratorPanel({ state, running }: OrchestratorPanelProps) {
  const tickets: TicketEntry[] = state?.tickets ?? [];
  const firstTicket = tickets[0];

  // Automation progress based on what's filled in
  const steps: unknown[] = [
    state?.issues,
    state?.remediations,
    state?.cookbook,
    tickets.length > 0 || undefined,
    state?.notification,
  ];
  const completed = steps.filter(Boolean).length;
  const pct = Math.round((completed / steps.length) * 100);

  const incidentId = firstTicket?.ticket.key ? `#${firstTicket.ticket.key}` : "#INC-2024";

  return (
    <div className="orchestrator-card">
      <p className="panel-section-title">Orchestrator</p>

      {/* Incident ID + Duration */}
      <div className="orchestrator-row">
        <div>
          <div className="orchestrator-label">Incident ID</div>
          <div className="orchestrator-value">{incidentId}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="orchestrator-label">Duration</div>
          <div className="orchestrator-value timer">
            {running ? "Running…" : state ? "Done" : "—"}
          </div>
        </div>
      </div>

      {/* Progress */}
      {(running || state) && (
        <div className="progress-section">
          <div className="progress-label-row">
            <span>Automation Progress</span>
            <span className="progress-pct">{pct}%</span>
          </div>
          <div className="progress-bar-track">
            <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {/* ITSM tickets — one per detected issue */}
      {tickets.map((entry) => (
        <a
          key={entry.ticket.key}
          href={entry.ticket.url ?? "#"}
          target="_blank"
          rel="noreferrer"
          className="jira-link-row"
        >
          <div className="jira-badge-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <rect width="24" height="24" rx="4" fill="#0052cc" />
              <path d="M12 4L4 12L12 20M12 4L20 12L12 20M12 4V20" stroke="#fff" strokeWidth="2" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="jira-text">
            {entry.ticket.key} · {entry.decision.path === "remediative" ? "🤖" : "🙋"}
            {entry.assigned_engineer ? ` · ${entry.assigned_engineer.name}` : ""}
          </span>
          <span className="jira-ext-icon">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15,3 21,3 21,9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
          </span>
        </a>
      ))}

      {!state && !running && (
        <p className="empty-state" style={{ padding: "var(--space-2) 0" }}>
          Run analysis to see incident details
        </p>
      )}
    </div>
  );
}

// ─── Slack Panel ──────────────────────────────────────────────────────────────

interface SlackPanelProps {
  slackResult: NotificationResult | undefined;
}

function SlackPanel({ slackResult }: SlackPanelProps) {
  if (!slackResult) {
    return (
      <div className="slack-panel">
        <div className="slack-header">
          <p className="panel-section-title" style={{ marginBottom: 0 }}>Slack Output</p>
        </div>
        <p className="empty-state" style={{ padding: "var(--space-4) 0" }}>
          Slack notification will appear here
        </p>
      </div>
    );
  }

  const channel = slackResult.channel ?? "#incidents";
  const text = slackResult.text_preview ?? "";
  const lines = text.split("\n\n").filter(Boolean);

  return (
    <div className="slack-panel">
      <div className="slack-header">
        <p className="panel-section-title" style={{ marginBottom: 0 }}>Slack Output</p>
        <button className="terminal-action-btn" aria-label="Slack options">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" />
          </svg>
        </button>
      </div>

      {lines.slice(0, 2).map((line, i) => (
        <div key={i} className="slack-message">
          <div className="slack-avatar">🤖</div>
          <div className="slack-content">
            <div>
              <span className="slack-bot-name">OpsBot</span>
              <span className="slack-time">{i === 0 ? "Just now" : "moments ago"}</span>
            </div>
            <div className="slack-bubble">{line}</div>
          </div>
        </div>
      ))}

      <button className="slack-channel-btn">
        Open {channel} channel
      </button>
    </div>
  );
}

// ─── Reliability Card ─────────────────────────────────────────────────────────

interface ReliabilityCardProps {
  state: AnalysisResult | null;
}

function ReliabilityCard({ state }: ReliabilityCardProps) {
  const hasResult = state !== null;
  return (
    <div className="reliability-card">
      <div className="reliability-left">
        <div className="reliability-icon">🤖</div>
        <div>
          <div className="reliability-label">Agent Reliability</div>
          <div className="reliability-sub">
            {hasResult ? "All agents completed successfully" : "Monitoring agent health…"}
          </div>
        </div>
      </div>
      <div className="reliability-badge">
        {hasResult ? "OPTIMIZED" : "READY"}
      </div>
    </div>
  );
}

// ─── Main Export ──────────────────────────────────────────────────────────────

interface RightPanelProps {
  state: AnalysisResult | null;
  running: boolean;
}

export default function RightPanel({ state, running }: RightPanelProps) {
  return (
    <aside className="right-panel">
      <OrchestratorPanel state={state} running={running} />
      <SlackPanel slackResult={state?.notification} />
      <ReliabilityCard state={state} />
    </aside>
  );
}
