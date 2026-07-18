---
name: ui-design
description: >
  Project-specific UI design skill for incident-suite. Triggers whenever building,
  redesigning, or improving any frontend UI (React/Vite). Covers design tokens,
  component patterns, animations, and visual excellence guidelines for the DevOps
  incident analysis dashboard. Use this skill for any task involving App.jsx,
  CSS, new components, dashboard layout, or UI aesthetics.
---

# UI Design Skill — incident-suite

## Visual Inspiration

The design is inspired by **OpsMind** — a premium DevOps operations dashboard.
Key visual traits:
- **Dark navy background** (#0e1117) with darker card surfaces (#161b27)
- **Electric blue accent** (#3b82f6 / bright cyan-blue) for interactive elements
- **macOS-style terminal window** with red/yellow/green traffic-light dots
- **3-column grid layout** (sidebar | main content | right panel)
- **Agent Swarm sidebar** with per-agent progress bars and status chips
- **Severity color-coding** directly in log line text (INFO=gray, WARN=yellow, ERROR=red, FATAL=red, CRITICAL=orange)
- **Compact Orchestrator panel** on the right showing incident ID, JIRA link, Slack chat

See `references/design_inspiration.md` for detailed breakdown.

---

## Tech Stack Constraints

| Concern       | Choice                        |
|---------------|-------------------------------|
| Framework     | React 18 + Vite 5             |
| Styling       | Vanilla CSS (plain `.css` files; no Tailwind, no CSS-in-JS) |
| Fonts         | Google Fonts — `Inter` (body) + `JetBrains Mono` (monospace/code) |
| Icons         | Inline SVG — never install an icon library |
| Animations    | CSS `@keyframes` + `transition` — no Framer Motion unless asked |
| State         | React `useState` / `useEffect` — no Redux/Zustand unless asked |
| API           | SSE streaming via `src/api.js` — DO NOT TOUCH |

> **CRITICAL**: Always import `./index.css` in `main.jsx`. All design tokens go in
> `index.css` as CSS custom properties (`:root { --token: value; }`).
> Never use inline `style={{}}` objects except for dynamic computed values.

---

## Design System

### Color Palette

```css
:root {
  /* === Backgrounds === */
  --bg-base:        #0a0e1a;    /* page background */
  --bg-surface:     #111827;    /* card / panel background */
  --bg-elevated:    #1a2235;    /* dropzone, hovered cards */
  --bg-terminal:    #0d1117;    /* terminal window background */
  --bg-glass:       rgba(255, 255, 255, 0.03);

  /* === Brand accent — electric blue === */
  --accent:         #3b82f6;
  --accent-bright:  #60a5fa;
  --accent-dim:     #1d4ed8;
  --accent-glow:    rgba(59, 130, 246, 0.20);

  /* === Severity === */
  --critical:       #ef4444;
  --critical-bg:    rgba(239, 68, 68, 0.12);
  --high:           #f97316;
  --high-bg:        rgba(249, 115, 22, 0.12);
  --medium:         #eab308;
  --medium-bg:      rgba(234, 179, 8, 0.12);
  --low:            #22c55e;
  --low-bg:         rgba(34, 197, 94, 0.12);

  /* === Log line severity colors === */
  --log-info:       #6b7280;
  --log-warn:       #eab308;
  --log-error:      #ef4444;
  --log-fatal:      #ef4444;
  --log-critical:   #f97316;
  --log-system:     #60a5fa;   /* system / AI agent lines */
  --log-system-bg:  rgba(59, 130, 246, 0.10);

  /* === Text === */
  --text-primary:   #e2e8f0;
  --text-secondary: #64748b;
  --text-muted:     #374151;
  --text-code:      #94a3b8;

  /* === Borders === */
  --border:         rgba(255, 255, 255, 0.07);
  --border-accent:  rgba(59, 130, 246, 0.35);

  /* === Agent states === */
  --agent-idle:     #1e293b;
  --agent-active:   #3b82f6;
  --agent-done:     #22c55e;
  --agent-error:    #ef4444;

  /* === Spacing === */
  --space-1: 4px;  --space-2: 8px;   --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px;  --space-8: 32px; --space-10: 40px;

  /* === Border radius === */
  --radius-sm: 6px;   --radius-md: 10px;
  --radius-lg: 16px;  --radius-full: 9999px;

  /* === Shadows === */
  --shadow-card:     0 2px 12px rgba(0, 0, 0, 0.5);
  --shadow-glow:     0 0 24px rgba(59, 130, 246, 0.30);
  --shadow-critical: 0 0 12px rgba(239, 68, 68, 0.25);

  /* === Transitions === */
  --transition-fast: 150ms ease;
  --transition-base: 250ms ease;
  --transition-slow: 400ms ease;

  /* === Typography === */
  --font-body: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --font-size-xs:   11px;
  --font-size-sm:   12px;
  --font-size-base: 14px;
  --font-size-md:   15px;
  --font-size-lg:   18px;
  --font-size-xl:   22px;
  --font-size-2xl:  28px;
}
```

---

## Layout Architecture (3-Column Dashboard)

```
┌──────────────────────────────────────────────────────────────────────┐
│  HEADER — Logo · Active Incidents · MTTR · User Avatar               │
├────────────┬─────────────────────────────┬───────────────────────────┤
│  LEFT      │  CENTER (flex: 1)           │  RIGHT                    │
│  (240px)   │                             │  (260px)                  │
│            │  ┌──────────────────────┐   │  ┌─────────────────────┐  │
│  INPUT     │  │ LOG TERMINAL         │   │  │ ORCHESTRATOR         │  │
│  LOGS      │  │ macOS-style window   │   │  │ Incident ID / Timer  │  │
│            │  │ with traffic lights  │   │  │ Progress bar         │  │
│  ──────    │  └──────────────────────┘   │  │ JIRA link            │  │
│            │                             │  └─────────────────────┘  │
│  AGENT     │  DETECTED ROOT CAUSES       │                           │
│  SWARM     │  Issue cards (2-col grid)   │  SLACK OUTPUT             │
│            │                             │  Chat-style messages      │
│            │  REMEDIATIONS               │                           │
│            │  Code blocks + copy btn     │  AGENT RELIABILITY        │
│            │                             │  Purple gradient card     │
│            │  INCIDENT COOKBOOK          │                           │
│            │  Numbered checklist         │                           │
└────────────┴─────────────────────────────┴───────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│  STATUS BAR — API Gateway: ONLINE · Latency · Keyboard shortcuts     │
└──────────────────────────────────────────────────────────────────────┘
```

Full viewport layout — no max-width container. Use CSS Grid:
```css
.dashboard-grid {
  display: grid;
  grid-template-columns: 240px 1fr 260px;
  grid-template-rows: auto 1fr auto;
  min-height: 100vh;
}
```

---

## Component Patterns

### 1. Header Bar

```css
.app-header {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  padding: 0 var(--space-5);
  height: 52px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}
```

Contains:
- Logo SVG + product name + version badge
- Spacer (`flex: 1`)
- "ACTIVE INCIDENTS" + count (in `var(--critical)`)
- "MTTR" + elapsed time
- Theme toggle (sun/moon SVG)
- User avatar initial circle

### 2. Left Sidebar Panel

```css
.left-panel {
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-5);
  overflow-y: auto;
}
```

Contains two sections:
- **INPUT LOGS** — DropZone + Run button
- **AGENT SWARM** — list of 5 agents with icon, name, status chip, progress bar

### 3. macOS Terminal Window

```css
.terminal-window {
  background: var(--bg-terminal);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.terminal-titlebar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: #1a1f2e;
  border-bottom: 1px solid var(--border);
}
.terminal-dot { width: 12px; height: 12px; border-radius: 50%; }
.terminal-dot.red    { background: #ff5f57; }
.terminal-dot.yellow { background: #ffbd2e; }
.terminal-dot.green  { background: #28c840; }
.terminal-filename {
  margin-left: var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.terminal-body {
  padding: var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: 1.8;
  overflow-y: auto;
  flex: 1;
  max-height: 340px;
  scrollbar-width: thin;
  scrollbar-color: #2d3748 transparent;
}
```

Log line coloring (applies color to the severity keyword, not the whole line):
```jsx
// Parse "[14:20:01] INFO message" into styled spans
function LogLine({ text }) {
  const match = text.match(/^(\[\d{2}:\d{2}:\d{2}\])?\s*(INFO|WARN|ERROR|FATAL|CRITICAL|\[System\])(.*)$/);
  if (!match) return <div className="log-line">{text}</div>;
  const [, time, level, msg] = match;
  const cls = `log-${level.replace(/[\[\]]/g,'').toLowerCase()}`;
  const isSystem = level === '[System]';
  return (
    <div className={`log-line ${isSystem ? 'log-line-system' : ''}`}>
      {time && <span className="log-time">{time} </span>}
      <span className={`log-level ${cls}`}>{level}</span>
      <span className="log-msg">{msg}</span>
    </div>
  );
}
```

```css
.log-line { display: flex; gap: 6px; }
.log-line-system { background: var(--log-system-bg); border-radius: 4px; padding: 1px 4px; }
.log-time     { color: var(--text-muted); }
.log-level    { font-weight: 600; min-width: 60px; }
.log-info     { color: var(--log-info); }
.log-warn     { color: var(--log-warn); }
.log-error    { color: var(--log-error); }
.log-fatal    { color: var(--log-fatal); }
.log-critical { color: var(--log-critical); }
.log-system   { color: var(--log-system); font-style: italic; }
.log-msg      { color: var(--text-code); }
```

### 4. Agent Swarm List

Each agent row:
```css
.agent-row {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  transition: border-color var(--transition-base);
}
.agent-row.is-active { border-color: var(--accent); }
.agent-row-top { display: flex; align-items: center; gap: var(--space-3); }
.agent-icon   { width: 32px; height: 32px; border-radius: var(--radius-sm); background: var(--bg-surface); display: flex; align-items: center; justify-content: center; }
.agent-name   { font-size: var(--font-size-base); font-weight: 600; flex: 1; }
.agent-status { font-size: var(--font-size-xs); }
.agent-progress-track { height: 3px; background: var(--border); border-radius: var(--radius-full); overflow: hidden; }
.agent-progress-fill  { height: 100%; border-radius: var(--radius-full); transition: width 0.6s ease; }
```

Status chip colors:
- idle → `color: var(--text-muted)`
- active → `color: var(--accent)` + `animation: pulse-text 1.4s infinite`
- done → `color: var(--agent-done)`

Progress bar colors: idle=`var(--border)` | active=`var(--accent)` | done=`var(--agent-done)`

### 5. Orchestrator Panel (Right)

```css
.orchestrator-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
}
.orchestrator-title { font-size: var(--font-size-xs); letter-spacing: 1.2px; color: var(--text-secondary); text-transform: uppercase; font-weight: 600; }
.incident-id   { font-size: var(--font-size-lg); font-weight: 700; color: var(--text-primary); font-family: var(--font-mono); }
.incident-timer { font-size: var(--font-size-lg); font-weight: 700; color: var(--accent); font-family: var(--font-mono); }
.progress-label { display: flex; justify-content: space-between; font-size: var(--font-size-xs); color: var(--text-secondary); margin-bottom: var(--space-1); }
.progress-bar   { height: 6px; background: var(--border); border-radius: var(--radius-full); overflow: hidden; }
.progress-fill  { height: 100%; background: linear-gradient(90deg, var(--accent-dim), var(--accent)); border-radius: var(--radius-full); transition: width 0.8s ease; }
```

### 6. Slack Output Panel (Right)

```css
.slack-panel { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-5); }
.slack-message { display: flex; gap: var(--space-3); padding: var(--space-3); border-radius: var(--radius-md); }
.slack-avatar  { width: 32px; height: 32px; border-radius: var(--radius-sm); background: #4a154b; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
.slack-bubble  { background: var(--bg-elevated); border-radius: 0 var(--radius-md) var(--radius-md) var(--radius-md); padding: var(--space-3); font-size: var(--font-size-sm); color: var(--text-primary); line-height: 1.5; }
.slack-time    { font-size: var(--font-size-xs); color: var(--text-muted); margin-bottom: var(--space-1); }
```

### 7. Issue / Root Cause Cards (2-column grid)

```css
.issues-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-4); }
.issue-card  { background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); transition: border-color var(--transition-base); animation: fade-in 300ms ease forwards; }
.issue-card:hover { border-color: var(--border-accent); }
.issue-card-header { display: flex; align-items: flex-start; gap: var(--space-3); }
.issue-card-icon   { width: 36px; height: 36px; border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 18px; }
.issue-card-title  { font-size: var(--font-size-base); font-weight: 700; line-height: 1.3; }
.issue-card-class  { font-size: var(--font-size-xs); color: var(--text-muted); letter-spacing: 0.5px; text-transform: uppercase; }
.issue-card-body   { font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.5; }
.issue-card-footer { display: flex; align-items: center; justify-content: space-between; margin-top: auto; }
```

### 8. Severity Badge

```css
.badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: var(--radius-full); font-size: var(--font-size-xs); font-weight: 700; letter-spacing: 0.8px; border: 1px solid; }
.badge-critical { background: var(--critical-bg); color: var(--critical); border-color: var(--critical); }
.badge-high     { background: var(--high-bg);     color: var(--high);     border-color: var(--high); }
.badge-medium   { background: var(--medium-bg);   color: var(--medium);   border-color: var(--medium); }
.badge-low      { background: var(--low-bg);      color: var(--low);      border-color: var(--low); }
```

### 9. DropZone

```css
.dropzone { border: 2px dashed rgba(59,130,246,0.25); border-radius: var(--radius-md); padding: var(--space-8) var(--space-4); text-align: center; cursor: pointer; transition: all var(--transition-base); color: var(--text-secondary); display: flex; flex-direction: column; align-items: center; gap: var(--space-3); }
.dropzone:hover:not(.disabled), .dropzone.dragging { border-color: var(--accent); background: var(--accent-glow); color: var(--accent-bright); }
.dropzone.has-file { border-style: solid; border-color: var(--accent); background: var(--accent-glow); }
```

### 10. Action Button

```css
.btn-primary { width: 100%; padding: var(--space-3) var(--space-4); background: var(--accent); color: #fff; font-weight: 600; font-size: var(--font-size-base); border: none; border-radius: var(--radius-md); cursor: pointer; transition: all var(--transition-fast); display: flex; align-items: center; justify-content: center; gap: var(--space-2); }
.btn-primary:hover:not(:disabled) { background: var(--accent-bright); box-shadow: var(--shadow-glow); }
.btn-primary:disabled { opacity: 0.45; cursor: not-allowed; }
```

---

## Animations / Keyframes (define in index.css)

```css
@keyframes fade-in      { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
@keyframes pulse-glow   { 0%,100% { box-shadow: 0 0 0 0 var(--accent-glow); } 50% { box-shadow: 0 0 0 6px transparent; } }
@keyframes pulse-text   { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
@keyframes spin         { to { transform: rotate(360deg); } }
@keyframes progress-bar { from { width: 0%; } }
@keyframes blink-cursor { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
```

---

## Status Bar

Fixed to the bottom of the page:
```css
.status-bar { grid-column: 1/-1; height: 28px; background: #070b14; border-top: 1px solid var(--border); display: flex; align-items: center; gap: var(--space-6); padding: 0 var(--space-5); font-size: var(--font-size-xs); color: var(--text-muted); }
.status-dot-green { width: 6px; height: 6px; border-radius: 50%; background: var(--agent-done); display: inline-block; margin-right: 4px; }
```

---

## File Structure

```
frontend/
├── index.html                 ← Google Fonts + meta
├── src/
│   ├── main.jsx               ← imports './index.css'
│   ├── index.css              ← ALL tokens + global styles + keyframes
│   ├── App.jsx                ← orchestrates layout, all state lives here
│   ├── api.js                 ← SSE (DO NOT MODIFY)
│   └── components/
│       ├── AppHeader.jsx      ← header bar
│       ├── LeftPanel.jsx      ← drop zone + agent swarm
│       ├── TerminalWindow.jsx ← macOS terminal chrome + log stream
│       ├── RightPanel.jsx     ← orchestrator + slack + reliability
│       └── Results.jsx        ← issues grid + remediations + cookbook
```

---

## Quality Checklist

- [ ] 3-column grid layout with full viewport height
- [ ] macOS traffic-light dots in terminal titlebar
- [ ] Agent rows show idle / active / done states with animated progress bars
- [ ] Log lines color-code severity keywords
- [ ] System/AI lines have blue background highlight
- [ ] Issues displayed in 2-column card grid
- [ ] Slack panel shows chat-bubble style messages
- [ ] Status bar fixed to bottom
- [ ] All colors use `var(--token)` — zero hardcoded hex in JSX
- [ ] Responsive: below 1024px collapse to single column
- [ ] No inline `style={{}}` except dynamic width values

---

## References

- `references/design_inspiration.md` — OpsMind breakdown
- `references/component_examples.md` — copy-paste snippets
- `frontend/src/api.js` — SSE streaming contract (stable, do not touch)
