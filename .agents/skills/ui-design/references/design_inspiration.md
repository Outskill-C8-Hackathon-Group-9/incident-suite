# Design Inspiration

These links and resources inspire the visual design of the incident-suite dashboard.
All designs use dark mode, glassmorphism, cyan accents, and monospace terminal aesthetics.

## Reference UIs

| Source                        | What to borrow                            |
|-------------------------------|-------------------------------------------|
| Grafana                       | Pipeline status nodes, alert severity colors |
| Datadog APM                   | Trace/span timeline, dark terminal panels |
| Linear                        | Card layout, subtle hover effects, clean typography |
| Vercel Dashboard              | File upload zone styling, status indicators |
| PlanetScale                   | Glassmorphism cards, gradient buttons |
| GitHub Actions                | Step-by-step pipeline status visualization |

## Color Principles

- **Base**: Near-black indigo (`#080d1a`) — warmer than pure black, avoids harshness
- **Accent**: Electric cyan (`#00d4ff`) — signals "live / active / system"
- **Critical**: Hot red-pink (`#ff4f6a`) — urgent, attention-grabbing
- **Success / Done**: Muted green (`#4ade80`) — calm, positive
- **Warning / High**: Orange (`#ff8c42`) — alert but not critical
- **Medium**: Amber (`#f5c518`) — caution

## Typography Inspiration

- **Inter** — the gold standard for developer dashboards (Linear, Vercel, Notion)
- **JetBrains Mono** — preferred by developers for all code/log output; ligature support

## Motion Principles

- All animations under 400ms
- Easing: `ease` or `cubic-bezier(0.4, 0, 0.2, 1)` (Material easing)
- Hover lifts: `translateY(-1px)` — subtle, not dramatic
- Active pulses: Use `box-shadow` keyframes, NOT `scale` (avoids layout reflow)
- Entry animations: `fade-in` (opacity + translateY) — universal, never jarring

## Terminal / Console Aesthetics

Reference: VS Code terminal, iTerm2 dark theme, Datadog Log Explorer

- Background: `#050810` (darker than the page to create depth)
- Text: `#9fe8ff` (soft cyan — easy to read, feels "techy")
- Left border: 3px solid `var(--accent)` — the "active pipe" indicator
- Scrollbar: thin, accent-colored track
- Font: JetBrains Mono 13px, line-height 1.6

## Glassmorphism Guidelines

- Use sparingly — only for cards and overlays
- `backdrop-filter: blur(12px)` with `background: rgba(255,255,255,0.04)`
- Always pair with a subtle `border: 1px solid rgba(255,255,255,0.08)` 
- Never use on elements that overlap other blurred elements (stacking blur = perf hit)
