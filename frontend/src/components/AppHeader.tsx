import { useEffect, useState } from "react";
import { UserButton, useAuth } from "@clerk/react";

interface AppHeaderProps {
  running: boolean;
  criticalCount: number;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
}

export default function AppHeader({ running, criticalCount }: AppHeaderProps) {
  const [elapsed, setElapsed] = useState<number>(0);
  const { signOut } = useAuth();

  useEffect(() => {
    if (!running) {
      setElapsed(0);
      return;
    }
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, [running]);

  return (
    <header className="app-header">
      <a href="/analyze" className="header-logo">
        <div className="header-logo-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><polygon points="13,2 3,14 12,14 11,22 21,10 12,10" /></svg>
        </div>
        <span className="header-logo-name">IncidentSuite</span>
      </a>
      <span className="header-version">v1.0</span>
      <div className="header-spacer" />
      <div className="header-stat"><span className="header-stat-label">Active Incidents</span><span className={`header-stat-value ${criticalCount > 0 ? "critical" : ""}`}>{criticalCount > 0 ? `${criticalCount} Critical` : "None"}</span></div>
      <div className="header-sep" />
      <div className="header-stat"><span className="header-stat-label">MTTR</span><span className="header-stat-value accent">{running || elapsed > 0 ? formatElapsed(elapsed) : "—"}</span></div>
      <div className="header-sep" />
      <div className="header-auth">
        <span className="header-user-label">Signed in</span>
        <UserButton />
        <button className="auth-btn auth-btn-secondary" type="button" onClick={() => { void signOut({ redirectUrl: "/login" }); }}>Sign out</button>
      </div>
    </header>
  );
}
