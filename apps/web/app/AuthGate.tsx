"use client";

// Client-side UX guard: render children only for a signed-in user, otherwise redirect to
// /login. NOT a security boundary — the api enforces auth on every endpoint (401). This
// just avoids showing a dead, unusable UI to logged-out visitors.

import { useEffect, useState } from "react";

const API_BASE = "/api";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"loading" | "ok">("loading");

  useEffect(() => {
    fetch(`${API_BASE}/v1/me`, { credentials: "include" })
      .then((res) => {
        if (res.ok) setState("ok");
        else window.location.href = "/login";
      })
      .catch(() => {
        window.location.href = "/login";
      });
  }, []);

  if (state !== "ok") {
    return (
      <main style={{ maxWidth: 480, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
        Loading…
      </main>
    );
  }
  return <>{children}</>;
}
