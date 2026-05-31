"use client";

// Ingest API key management: create (shown once), list, and revoke the keys that HAE and
// Apple Shortcuts use to authenticate. Calls the api cross-origin with the session cookie.

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Key = {
  id: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export default function ApiKeysPage() {
  const [state, setState] = useState<"loading" | "authed" | "anon">("loading");
  const [keys, setKeys] = useState<Key[]>([]);
  const [label, setLabel] = useState("iPhone HAE");
  const [newKey, setNewKey] = useState<string | null>(null);

  async function load() {
    const res = await fetch(`${API_BASE}/v1/api-keys`, { credentials: "include" });
    if (res.status === 401) {
      setState("anon");
      return;
    }
    setKeys(await res.json());
    setState("authed");
  }

  useEffect(() => {
    // Inline fetch chain (rather than calling the async load()) so state is only set
    // from async continuations, which the react-hooks lint rules expect.
    fetch(`${API_BASE}/v1/api-keys`, { credentials: "include" })
      .then((res) => {
        if (res.status === 401) {
          setState("anon");
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (data) {
          setKeys(data);
          setState("authed");
        }
      })
      .catch(() => setState("anon"));
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/v1/api-keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ label }),
    });
    if (res.ok) {
      setNewKey((await res.json()).key);
      await load();
    }
  }

  async function revoke(id: string) {
    await fetch(`${API_BASE}/v1/api-keys/${id}`, { method: "DELETE", credentials: "include" });
    await load();
  }

  if (state === "loading") return <Shell>Loading...</Shell>;
  if (state === "anon")
    return (
      <Shell>
        You are not signed in. <a href="/login">Sign in</a>.
      </Shell>
    );

  return (
    <Shell>
      {newKey && (
        <div style={{ border: "1px solid #0a0", padding: 12, marginBottom: 16 }}>
          <strong>Copy this key now. It will not be shown again:</strong>
          <pre style={{ overflowX: "auto" }}>{newKey}</pre>
        </div>
      )}
      <form onSubmit={create} style={{ marginBottom: 16 }}>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label"
          style={{ padding: 8, marginRight: 8 }}
        />
        <button type="submit" style={{ padding: "8px 16px" }}>
          Create key
        </button>
      </form>
      <ul style={{ paddingLeft: 0, listStyle: "none" }}>
        {keys.map((k) => (
          <li key={k.id} style={{ marginBottom: 8 }}>
            <strong>{k.label}</strong> {k.revoked_at ? "(revoked)" : ""}{" "}
            <span style={{ color: "#666" }}>
              created {new Date(k.created_at).toLocaleDateString()}
              {k.last_used_at ? `, last used ${new Date(k.last_used_at).toLocaleString()}` : ""}
            </span>{" "}
            {!k.revoked_at && (
              <button onClick={() => revoke(k.id)} style={{ marginLeft: 8 }}>
                Revoke
              </button>
            )}
          </li>
        ))}
      </ul>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Ingest API keys</h1>
      <p style={{ color: "#666" }}>
        Keys authenticate Health Auto Export and Apple Shortcuts. They can only ingest
        data, not read it or change settings.
      </p>
      {children}
    </main>
  );
}
