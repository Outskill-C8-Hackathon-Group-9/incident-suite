import { useState } from "react";
import type {
  Issue,
  Remediation,
  Cookbook,
  CookbookItem,
  AnalysisResult,
  Severity,
  TicketEntry,
} from "../types";

// ─── Sub-components ────────────────────────────────────────────────────────────

interface SeverityBadgeProps {
  severity: Severity | string | undefined;
}

function SeverityBadge({ severity }: SeverityBadgeProps) {
  if (!severity) return null;
  return (
    <span className={`badge badge-${severity.toLowerCase()}`}>
      {severity.toUpperCase()}
    </span>
  );
}

function issueIcon(severity: string | undefined): string {
  const s = (severity ?? "").toLowerCase();
  if (s === "critical") return "🔴";
  if (s === "high")     return "🟠";
  if (s === "medium")   return "🟡";
  return "🟢";
}

interface CopyButtonProps {
  text: string | undefined;
}

function CopyButton({ text }: CopyButtonProps) {
  const [copied, setCopied] = useState<boolean>(false);
  const copy = () => {
    void navigator.clipboard.writeText(text ?? "").then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button className={`copy-btn ${copied ? "copied" : ""}`} onClick={copy}>
      {copied ? "✓ Copied" : "Copy"}
    </button>
  );
}

// ─── Section components ────────────────────────────────────────────────────────

interface IssuesSectionProps {
  issues: Issue[] | undefined;
}

function IssuesSection({ issues }: IssuesSectionProps) {
  if (!issues?.length) return null;
  return (
    <section>
      <h2 className="section-heading">
        Detected Root Causes
        <span className="section-badge">{issues.length}</span>
      </h2>
      <div className="issues-grid" style={{ marginTop: "var(--space-4)" }}>
        {issues.map((issue) => (
          <div key={issue.id} className="issue-card">
            <div className="issue-card-header">
              <div className={`issue-card-icon ${(issue.severity ?? "").toLowerCase()}`}>
                {issueIcon(issue.severity)}
              </div>
              <div className="issue-card-meta">
                <div className="issue-card-title">{issue.title}</div>
                <div className="issue-card-class">
                  Classification: {issue.affected_service ?? "Unknown"}
                </div>
              </div>
            </div>
            <p className="issue-card-body">{issue.summary}</p>
            <div className="issue-card-footer">
              <SeverityBadge severity={issue.severity} />
              {issue.affected_service && (
                <span className="issue-service-chip">{issue.affected_service}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

interface RemediationsSectionProps {
  remediations: Remediation[] | undefined;
}

function RemediationsSection({ remediations }: RemediationsSectionProps) {
  if (!remediations?.length) return null;
  return (
    <section>
      <h2 className="section-heading">Remediations (RAG-grounded)</h2>
      <div className="results-stack" style={{ marginTop: "var(--space-4)" }}>
        {remediations.map((r) => (
          <div key={r.issue_id} className="remediation-card">
            <div className="remediation-id">Issue #{r.issue_id}</div>
            <div className="remediation-summary">{r.fix_summary}</div>
            {r.suggested_command && (
              <div className="code-block">
                <pre className="code-pre">{r.suggested_command}</pre>
                <CopyButton text={r.suggested_command} />
              </div>
            )}
            {r.rationale && (
              <p className="remediation-rationale">{r.rationale}</p>
            )}
            {(r.grounded_in?.length ?? 0) > 0 && (
              <div className="remediation-grounded">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                </svg>
                Grounded in: {r.grounded_in?.join(", ")}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

interface CookbookSectionProps {
  cookbook: Cookbook | undefined;
}

function CookbookSection({ cookbook }: CookbookSectionProps) {
  if (!cookbook) return null;
  return (
    <section>
      <h2 className="section-heading">{cookbook.title ?? "Incident Cookbook"}</h2>
      <div className="cookbook-list" style={{ marginTop: "var(--space-4)" }}>
        {cookbook.items?.map((item: CookbookItem) => (
          <div key={item.step} className="cookbook-item">
            <div className="cookbook-step-num">{item.step}</div>
            <div>
              <div className="cookbook-action">{item.action}</div>
              <div className="cookbook-meta">
                {item.owner_hint && (
                  <span className="cookbook-owner">👤 {item.owner_hint}</span>
                )}
                {item.done_when && (
                  <span className="cookbook-done-when">✓ {item.done_when}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

interface TicketsSectionProps {
  tickets: TicketEntry[] | undefined;
}

function TicketsSection({ tickets }: TicketsSectionProps) {
  if (!tickets?.length) return null;
  return (
    <section>
      <h2 className="section-heading">
        Incident Tickets
        <span className="section-badge">{tickets.length}</span>
      </h2>
      <div className="results-stack" style={{ marginTop: "var(--space-4)" }}>
        {tickets.map((entry) => {
          const { decision, ticket, execution, verification, assigned_engineer } = entry;
          const remediative = decision.path === "remediative";
          return (
            <div key={ticket.key} className="remediation-card">
              <div className="remediation-id">
                {remediative ? "🤖 Remediative" : "🙋 Investigative"} · {ticket.key}
                {entry.duplicate_found ? " (duplicate — reused existing ticket)" : ""}
              </div>
              <div className="remediation-summary">{entry.title}</div>
              <p className="remediation-rationale">{decision.policy_reason}</p>
              <p className="remediation-rationale">
                Status: {ticket.status}
                {assigned_engineer ? ` · Assigned: ${assigned_engineer.name} (${assigned_engineer.expertise || "generalist"})` : ""}
              </p>
              {execution && <p className="remediation-rationale">{execution.summary}</p>}
              {verification && (
                <p className="remediation-rationale">
                  {verification.success ? "✅" : "⏳"} {verification.details}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────

interface ResultsProps {
  state: AnalysisResult | null;
}

export default function Results({ state }: ResultsProps) {
  if (!state) return null;
  return (
    <div className="results-stack">
      <IssuesSection issues={state.issues} />
      <RemediationsSection remediations={state.remediations} />
      <CookbookSection cookbook={state.cookbook} />
      <TicketsSection tickets={state.tickets} />
    </div>
  );
}
