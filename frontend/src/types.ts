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
  rag_hits?: "cookbook" | "db" | null;
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
  title?: string | null;
  severity?: Severity | null;
  rag_hits?: "cookbook" | "db" | null;
}

/** The incident cookbook returned by the cookbook-builder agent */
export interface Cookbook {
  title?: string;
  items: CookbookItem[];
}

/** Path chosen by the decision engine */
export type ResponsePath = "remediative" | "investigative";

/** The decision-engine verdict: remediative (auto-fix) vs investigative (human) */
export interface Decision {
  path: ResponsePath;
  severity: Severity | string;
  confidence: number;
  policy_reason: string;
  matched_signals?: string[];
  reference_sources?: string[];
}

/** An ITSM ticket created for one detected issue */
export interface JiraTicket {
  key: string;
  url: string;
  summary: string;
  severity: string;
  status: string;
  assignee?: string;
}

/** An on-call engineer from the roster */
export interface Engineer {
  name: string;
  email?: string;
  slack_user_id?: string;
  jira_account_id?: string;
  expertise?: string;
}

/** Result of auto-executing the cookbook (remediative path only) */
export interface ExecutionResult {
  steps_run: string[];
  summary: string;
}

/** Result of verifying the auto-fix (remediative path only) */
export interface VerificationResult {
  success: boolean;
  details: string;
}

/** The Slack notification result from the notify_slack agent */
export interface NotificationResult {
  channel: string;
  team_permalink?: string;
  dm_permalink?: string;
  text_preview: string;
}

/** One incident: the issue's decision, ticket, and (if remediative) fix outcome */
export interface TicketEntry {
  issue_id: string;
  title: string;
  decision: Decision;
  ticket: JiraTicket;
  assigned_engineer?: Engineer | null;
  duplicate_found: boolean;
  execution?: ExecutionResult;
  verification?: VerificationResult;
}

/** The final state object emitted by the `done` SSE event */
export interface AnalysisResult {
  issues?: Issue[];
  remediations?: Remediation[];
  cookbook?: Cookbook;
  tickets?: TicketEntry[];
  notification?: NotificationResult;
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
export type AgentId =
  | "classifier"
  | "remediation"
  | "cookbook"
  | "decide_response"
  | "create_ticket"
  | "execute_cookbook"
  | "verify_outcome"
  | "close_ticket"
  | "notify_slack";

/** A single entry in the Agent Swarm list */
export interface AgentMeta {
  id: AgentId;
  label: string;
  icon: string;
}

/** Map of node-id → boolean used for active/done state */
export type NodeStateMap = Partial<Record<string, boolean>>;
