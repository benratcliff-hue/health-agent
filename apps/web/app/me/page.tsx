"use client";

// Authenticated view: fetches the current user from the API using the session cookie.
// Must run in the browser (the cookie lives on the api domain), so this is a client
// component fetching with credentials, not a server component.

import { useEffect, useState } from "react";

// Same-origin: proxied to the backend by next.config.ts so the session cookie is sent.
const API_BASE = "/api";

type Me = { id: string; email: string; name: string; role: string };

export default function MePage() {
  const [state, setState] = useState<"loading" | "authed" | "anon">("loading");
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/v1/me`, { credentials: "include" })
      .then((res) => {
        if (res.status === 200) return res.json();
        if (res.status === 401) {
          setState("anon");
          return null;
        }
        throw new Error(`unexpected ${res.status}`);
      })
      .then((data) => {
        if (data) {
          setMe(data);
          setState("authed");
        }
      })
      .catch(() => setState("anon"));
  }, []);

  async function logout() {
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
    window.location.href = "/login";
  }

  return (
    <main style={{ maxWidth: 480, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Your account</h1>
      {state === "loading" && <p>Loading...</p>}
      {state === "anon" && (
        <p>
          You are not signed in. <a href="/login">Sign in</a>.
        </p>
      )}
      {state === "authed" && me && (
        <>
          <p>
            Signed in as <strong>{me.name}</strong> ({me.email}), role {me.role}.
          </p>
          <p>
            <a href="/chat">Chat with your coach</a>
          </p>
          <p>
            <a href="/settings/keys">Manage ingest API keys</a>
          </p>
          <p>
            {/* Top-level navigation so the session cookie (SameSite=Lax) is sent to the
                api, which redirects on to Whoop's consent screen. */}
            <a href={`${API_BASE}/v1/whoop/connect`}>Connect Whoop</a>
          </p>
          <button onClick={logout} style={{ padding: "8px 16px" }}>
            Log out
          </button>
        </>
      )}
    </main>
  );
}
