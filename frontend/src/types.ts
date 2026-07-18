// ─────────────────────────────────────────────────────────────────────────────
// Shared domain types for the Incident Suite frontend.
// All backend response shapes are modelled here.
// ─────────────────────────────────────────────────────────────────────────────

/** Severity levels emitted by the classifier agent */
export type Severity = "critical" | "high" | "medium" | "low";

/** A single trace / log entry streamed by an agent node */
export interface TraceEntry {
  node: string;
  message: string;
}

/** A detected incident issue returned by the classifier */
export interface Issue {
  id: string;
  title: string;
  severity: Severity;
  affected_service: string;
  summary: string;
}

/** A RAG-grounded remediation for a specific issue */
export interface Remediation {
  issue_id: string;
  fix_summary: string;
  suggested_command?: string;
  rationale?: string;
  grounded_in?: string[];
}

/** A single step inside the incident cookbook */
export interface CookbookItem {
  step: number;
  action: string;
  owner_hint?: string;
  done_when?: string;
}

/** The incident cookbook returned by the cookbook-builder agent */
export interface Cookbook {
  title?: string;
  items: CookbookItem[];
}

/** A JIRA ticket created by the jira-integrator agent */
export interface JiraTicket {
  key: string;
  url: string;
  summary: string;
  severity: string;
}

/** The Slack notification result from the notifier agent */
export interface SlackResult {
  channel: string;
  text_preview: string;
}

/** The final state object emitted by the `done` SSE event */
export interface AnalysisResult {
  issues?: Issue[];
  remediations?: Remediation[];
  cookbook?: Cookbook;
  jira_tickets?: JiraTicket[];
  slack_result?: SlackResult;
}

// ─── SSE / API contract types ─────────────────────────────────────────────────

/** Payload carried inside a `node` SSE event */
export interface NodeUpdate {
  trace?: TraceEntry[];
  [key: string]: unknown;
}

/** Full `node` event envelope received from the stream */
export interface NodeEvent {
  node: string;
  update?: NodeUpdate;
}

/** Callback bag passed to `analyze()` */
export interface AnalyzeCallbacks {
  onNode?: (event: NodeEvent) => void;
  onDone?: (state: AnalysisResult) => void;
  onError?: (error: Error) => void;
}

// ─── Agent / UI types ─────────────────────────────────────────────────────────

/** Agent node identifier — matches the keys in `active` / `done` maps */
export type AgentId = "classifier" | "remediation" | "cookbook" | "notifier" | "jira";

/** A single entry in the Agent Swarm list */
export interface AgentMeta {
  id: AgentId;
  label: string;
  icon: string;
}

/** Map of node-id → boolean used for active/done state */
export type NodeStateMap = Partial<Record<string, boolean>>;
