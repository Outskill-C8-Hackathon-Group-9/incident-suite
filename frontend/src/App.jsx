import { useState } from "react";
import { analyze } from "./api";

const NODES = ["classifier", "remediation", "cookbook", "jira", "notifier"];
const LABELS = {
  classifier: "Log Reader / Classifier",
  remediation: "Remediation (RAG)",
  cookbook: "Cookbook Synthesizer",
  jira: "JIRA Tickets",
  notifier: "Slack Notification",
};

export default function App() {
  const [file, setFile] = useState(null);
  const [active, setActive] = useState({});
  const [trace, setTrace] = useState([]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!file) return;
    setRunning(true);
    setActive({});
    setTrace([]);
    setResult(null);
    setError(null);
    await analyze(file, {
      onNode: ({ node, update }) => {
        setActive((a) => ({ ...a, [node]: true }));
        if (update?.trace) setTrace((t) => [...t, ...update.trace]);
      },
      onDone: (finalState) => {
        setResult(finalState);
        setRunning(false);
      },
      onError: (err) => {
        setError(String(err));
        setRunning(false);
      },
    });
  };

  return (
    <div style={{ maxWidth: 920, margin: "2rem auto", fontFamily: "system-ui", padding: "0 1rem" }}>
      <h1>DevOps Incident Analysis Suite</h1>
      <p style={{ color: "#6b7280" }}>
        Upload ops logs. Five LangGraph agents detect issues, retrieve matching runbooks (RAG),
        propose fixes, build a checklist, file JIRA tickets for critical issues, and notify Slack.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "1rem 0" }}>
        <input
          type="file"
          accept=".log,.txt,.json"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button onClick={run} disabled={!file || running}>
          {running ? "Analyzing…" : "Analyze logs"}
        </button>
      </div>

      {error && <div style={{ color: "#b91c1c" }}>Error: {error}</div>}

      <div style={{ display: "flex", gap: 8, margin: "1rem 0", flexWrap: "wrap" }}>
        {NODES.map((n) => (
          <div
            key={n}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              background: active[n] ? "#16a34a" : "#e5e7eb",
              color: active[n] ? "#fff" : "#374151",
              fontSize: 13,
            }}
          >
            {LABELS[n]}
          </div>
        ))}
      </div>

      <div
        style={{
          background: "#0b1020",
          color: "#9fe8ff",
          padding: 12,
          borderRadius: 8,
          fontFamily: "monospace",
          fontSize: 12,
          minHeight: 80,
        }}
      >
        {trace.length === 0 && <div style={{ opacity: 0.5 }}>Trace will stream here…</div>}
        {trace.map((t, i) => (
          <div key={i}>
            [{t.node}] {t.message}
          </div>
        ))}
      </div>

      {result && <Results state={result} />}
    </div>
  );
}

function Card({ children }) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, margin: "8px 0" }}>
      {children}
    </div>
  );
}

function Results({ state }) {
  const tickets = state.jira_tickets || [];
  return (
    <div style={{ marginTop: 24 }}>
      <h2>Detected issues</h2>
      {(state.issues || []).map((i) => (
        <Card key={i.id}>
          <b>
            [{i.severity.toUpperCase()}] {i.title}
          </b>{" "}
          — <i>{i.affected_service}</i>
          <p style={{ margin: "6px 0 0" }}>{i.summary}</p>
        </Card>
      ))}

      <h2>Remediations (RAG-grounded)</h2>
      {(state.remediations || []).map((r) => (
        <Card key={r.issue_id}>
          <b>{r.issue_id}</b>: {r.fix_summary}
          <pre style={{ background: "#f3f4f6", padding: 8, overflowX: "auto" }}>
            {r.suggested_command}
          </pre>
          <div style={{ fontSize: 13, color: "#374151" }}>{r.rationale}</div>
          {r.grounded_in?.length > 0 && (
            <div style={{ fontSize: 12, color: "#2563eb", marginTop: 6 }}>
              grounded in: {r.grounded_in.join(", ")}
            </div>
          )}
        </Card>
      ))}

      {state.cookbook && (
        <>
          <h2>{state.cookbook.title}</h2>
          <ol>
            {state.cookbook.items.map((it) => (
              <li key={it.step} style={{ marginBottom: 6 }}>
                {it.action} <i>({it.owner_hint})</i>
                <br />
                <small style={{ color: "#6b7280" }}>done when: {it.done_when}</small>
              </li>
            ))}
          </ol>
        </>
      )}

      {tickets.length > 0 && (
        <>
          <h2>JIRA tickets created</h2>
          <ul>
            {tickets.map((t) => (
              <li key={t.key}>
                <a href={t.url} target="_blank" rel="noreferrer">
                  {t.key}
                </a>{" "}
                — {t.summary} ({t.severity})
              </li>
            ))}
          </ul>
        </>
      )}

      {state.slack_result && (
        <>
          <h2>Slack notification → {state.slack_result.channel}</h2>
          <pre
            style={{
              background: "#4a154b",
              color: "#fff",
              padding: 12,
              borderRadius: 8,
              whiteSpace: "pre-wrap",
            }}
          >
            {state.slack_result.text_preview}
          </pre>
        </>
      )}
    </div>
  );
}