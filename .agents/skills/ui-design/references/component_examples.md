# Component Examples — incident-suite UI

Full copy-paste component snippets for common patterns.

---

## DropZone.jsx

```jsx
import { useRef, useState } from 'react';

export default function DropZone({ onFile, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState(null);

  const handleFile = (f) => {
    if (!f) return;
    setFileName(f.name);
    onFile(f);
  };

  return (
    <div
      className={`dropzone ${dragging ? 'dragging' : ''} ${disabled ? 'disabled' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFile(e.dataTransfer.files[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".log,.txt,.json"
        style={{ display: 'none' }}
        onChange={(e) => handleFile(e.target.files[0])}
      />
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17,8 12,3 7,8"/>
        <line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
      <p className="dropzone-label">
        {fileName ? fileName : 'Drop your log file here, or click to browse'}
      </p>
      <p className="dropzone-hint">.log · .txt · .json</p>
    </div>
  );
}
```

CSS for DropZone in `index.css`:
```css
.dropzone {
  border: 2px dashed var(--border-accent);
  border-radius: var(--radius-lg);
  padding: var(--space-10) var(--space-8);
  text-align: center;
  cursor: pointer;
  transition: all var(--transition-base);
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}
.dropzone:hover:not(.disabled),
.dropzone.dragging {
  border-color: var(--accent);
  background: var(--accent-glow);
  color: var(--accent);
}
.dropzone.disabled { opacity: 0.5; cursor: not-allowed; }
.dropzone-label { font-size: var(--font-size-base); font-weight: 500; margin: 0; }
.dropzone-hint  { font-size: var(--font-size-xs); opacity: 0.6; margin: 0; }
```

---

## Pipeline.jsx

```jsx
const NODES = [
  { id: 'classifier',  label: 'Log Classifier',     icon: '🔍' },
  { id: 'remediation', label: 'Remediation (RAG)',   icon: '🧠' },
  { id: 'cookbook',    label: 'Cookbook Builder',    icon: '📋' },
  { id: 'jira',        label: 'JIRA Tickets',        icon: '🎫' },
  { id: 'notifier',    label: 'Slack Notifier',      icon: '💬' },
];

export default function Pipeline({ active, done }) {
  return (
    <div className="pipeline">
      {NODES.map((node, idx) => {
        const isDone   = done?.[node.id];
        const isActive = !isDone && active?.[node.id];
        const stateClass = isDone ? 'done' : isActive ? 'active' : 'idle';
        return (
          <div key={node.id} className="pipeline-step">
            <div className={`pipeline-node node-${stateClass}`}>
              <span>{node.icon}</span>
              {isDone && <span className="node-check">✓</span>}
            </div>
            <span className="pipeline-label">{node.label}</span>
            {idx < NODES.length - 1 && <div className={`pipeline-connector ${isDone ? 'active' : ''}`} />}
          </div>
        );
      })}
    </div>
  );
}
```

CSS for Pipeline in `index.css`:
```css
.pipeline {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-6) 0;
  overflow-x: auto;
}
.pipeline-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  position: relative;
  flex: 1;
  min-width: 100px;
}
.pipeline-node {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  position: relative;
  transition: all var(--transition-base);
  background: var(--node-idle);
}
.node-active {
  border-color: var(--node-active);
  background: var(--bg-elevated);
  animation: pulse-glow 1.4s ease-in-out infinite;
}
.node-done {
  border-color: var(--node-done);
  background: rgba(74, 222, 128, 0.1);
}
.node-check {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 16px;
  height: 16px;
  background: var(--node-done);
  border-radius: var(--radius-full);
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #000;
  font-weight: 700;
}
.pipeline-label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  text-align: center;
  max-width: 80px;
}
.pipeline-connector {
  position: absolute;
  top: 24px;
  left: calc(50% + 28px);
  right: calc(-50% + 28px);
  height: 2px;
  background: var(--border);
  transition: background var(--transition-slow);
}
.pipeline-connector.active { background: var(--node-done); }
```

---

## TraceConsole.jsx

```jsx
import { useEffect, useRef } from 'react';

export default function TraceConsole({ entries }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  return (
    <div className="trace-console">
      {entries.length === 0
        ? <span className="trace-empty">Trace will stream here once analysis starts…</span>
        : entries.map((entry, i) => (
            <div key={i} className="trace-line">
              <span className="trace-node">[{entry.node}]</span>
              <span className="trace-msg">{entry.message}</span>
            </div>
          ))
      }
      <div ref={bottomRef} />
    </div>
  );
}
```

CSS for TraceConsole in `index.css`:
```css
.trace-console {
  background: #050810;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--text-code);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  min-height: 80px;
  max-height: 280px;
  overflow-y: auto;
  line-height: 1.7;
  scrollbar-width: thin;
  scrollbar-color: var(--accent-dim) transparent;
}
.trace-empty { opacity: 0.35; font-style: italic; }
.trace-line  { display: flex; gap: var(--space-2); }
.trace-node  { color: var(--accent); font-weight: 500; flex-shrink: 0; }
.trace-msg   { color: var(--text-code); opacity: 0.85; }
```

---

## Severity Badge

```jsx
export function SeverityBadge({ severity }) {
  return (
    <span className={`badge badge-${severity.toLowerCase()}`}>
      {severity.toUpperCase()}
    </span>
  );
}
```

CSS:
```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.8px;
  border: 1px solid;
}
.badge-critical { background: var(--critical-bg); color: var(--critical); border-color: var(--critical); }
.badge-high     { background: var(--high-bg);     color: var(--high);     border-color: var(--high); }
.badge-medium   { background: var(--medium-bg);   color: var(--medium);   border-color: var(--medium); }
.badge-low      { background: var(--low-bg);      color: var(--low);      border-color: var(--low); }
```

---

## Code Block with Copy Button

```jsx
import { useState } from 'react';

export function CodeBlock({ code }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="code-block">
      <pre className="code-pre">{code}</pre>
      <button className="copy-btn" onClick={copy}>
        {copied ? '✓ Copied' : 'Copy'}
      </button>
    </div>
  );
}
```

CSS:
```css
.code-block {
  position: relative;
  margin: var(--space-3) 0;
}
.code-pre {
  background: #0a0f1e;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-4) var(--space-10) var(--space-4) var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--text-code);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
.copy-btn {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  padding: 2px 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.copy-btn:hover { border-color: var(--accent); color: var(--accent); }
```

---

## Global CSS Reset + Body

Always place at the TOP of `index.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: var(--font-body);
  font-size: var(--font-size-base);
  background: var(--bg-base);
  color: var(--text-primary);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3, h4 { font-weight: 700; line-height: 1.2; }

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

section-heading {
  border-left: 3px solid var(--accent);
  padding-left: var(--space-3);
  color: var(--text-primary);
  font-size: var(--font-size-xl);
  margin: var(--space-8) 0 var(--space-4);
}

.container {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-8) var(--space-4);
}
```
