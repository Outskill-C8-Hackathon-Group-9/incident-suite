import { AuthenticateWithRedirectCallback, useClerk } from "@clerk/react";

interface LoginPageProps {
  isCallback: boolean;
}

export default function LoginPage({ isCallback }: LoginPageProps) {
  const { client } = useClerk();

  if (isCallback) {
    return <AuthenticateWithRedirectCallback signInForceRedirectUrl="/analyze" />;
  }

  const continueWithGoogle = () => {
    void client.signIn.authenticateWithRedirect({
      strategy: "oauth_google",
      redirectUrl: "/login/sso-callback",
      redirectUrlComplete: "/analyze",
    });
  };

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-logo" aria-hidden="true">
          <svg width="27" height="27" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polygon points="13,2 3,14 12,14 11,22 21,10 12,10" />
          </svg>
        </div>
        <p className="login-eyebrow">INCIDENT OPERATIONS</p>
        <h1 id="login-title">IncidentSuite</h1>
        <p className="login-subtitle">Securely investigate incidents, pinpoint root causes, and coordinate remediation.</p>
        <button className="google-sign-in" type="button" onClick={continueWithGoogle}>
          <svg className="google-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="#4285F4" d="M21.35 12.24c0-.71-.06-1.39-.18-2.04H12v3.86h5.24a4.48 4.48 0 0 1-1.94 2.94v2.5h3.14c1.84-1.69 2.91-4.19 2.91-7.26Z" />
            <path fill="#34A853" d="M12 21.75c2.63 0 4.84-.87 6.45-2.35L15.31 17a5.8 5.8 0 0 1-8.63-3.05H3.44v2.58A9.75 9.75 0 0 0 12 21.75Z" />
            <path fill="#FBBC05" d="M6.68 13.95a5.87 5.87 0 0 1 0-3.9V7.47H3.44a9.74 9.74 0 0 0 0 9.06l3.24-2.58Z" />
            <path fill="#EA4335" d="M12 6.25c1.52 0 2.88.52 3.95 1.55l2.96-2.96C16.84 2.92 14.63 2.25 12 2.25a9.75 9.75 0 0 0-8.56 5.22l3.24 2.58A5.8 5.8 0 0 1 12 6.25Z" />
          </svg>
          Continue with Google
        </button>
        <p className="login-footer">Protected by Clerk</p>
      </section>
    </main>
  );
}