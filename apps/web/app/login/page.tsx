"use client";

// Login page: enter an email, request a magic link. The API is the auth authority, so
// we POST cross-origin with credentials so it can set the session cookie on callback.

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function LoginForm() {
  // The callback redirects here with ?error=invalid_link when a link is bad/expired.
  // Reading it during render (rather than in an effect) keeps state derivation explicit.
  const params = useSearchParams();
  const linkError =
    params.get("error") === "invalid_link"
      ? "That login link was invalid or expired. Request a new one."
      : null;

  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const error = submitError ?? linkError;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/magic-link`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error(`request failed (${res.status})`);
      setSent(true);
    } catch (err) {
      setSubmitError(String(err));
    }
  }

  return (
    <>
      {error && <p style={{ color: "#b00020" }}>{error}</p>}
      {sent ? (
        <p>
          If that email has an account, a login link is on its way. Check your inbox (and,
          in local dev, the api server logs).
        </p>
      ) : (
        <form onSubmit={onSubmit}>
          <label style={{ display: "block", marginBottom: 8 }}>
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
            />
          </label>
          <button type="submit" style={{ padding: "8px 16px" }}>
            Send me a login link
          </button>
        </form>
      )}
    </>
  );
}

export default function LoginPage() {
  return (
    <main style={{ maxWidth: 480, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Sign in</h1>
      <Suspense fallback={<p>Loading...</p>}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
