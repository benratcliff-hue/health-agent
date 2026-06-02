"use client";

// Self-service settings: timezone (drives 6am/8pm briefing times) and coach tone.
// Reads/writes /v1/me through the same-origin /api proxy.

import { useEffect, useState } from "react";

import AuthGate from "../AuthGate";

const API_BASE = "/api";

const TIMEZONES = [
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "America/Anchorage",
  "Pacific/Honolulu",
  "Europe/London",
  "UTC",
];

function SettingsInner() {
  const [timezone, setTimezone] = useState("UTC");
  const [tone, setTone] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/v1/me`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((me) => {
        if (me) {
          setTimezone(me.timezone ?? "UTC");
          setTone(me.coach_tone ?? "");
        }
      })
      .catch(() => {});
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setStatus("Saving…");
    const res = await fetch(`${API_BASE}/v1/me`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ timezone, coach_tone: tone }),
    });
    setStatus(res.ok ? "Saved." : `Error (${res.status})`);
  }

  return (
    <main style={{ maxWidth: 480, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Settings</h1>
      <p style={{ color: "#666" }}>
        <a href="/me">Account</a>
      </p>
      <form onSubmit={save} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <label>
          Timezone (when your 6am / 8pm briefings send)
          <select
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
          >
            {TIMEZONES.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </label>
        <label>
          Coach tone (optional)
          <input
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            placeholder="e.g. supportive, concise, data-forward"
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
          />
        </label>
        <div>
          <button type="submit" style={{ padding: "8px 16px" }}>
            Save
          </button>{" "}
          <span style={{ color: "#666" }}>{status}</span>
        </div>
      </form>
    </main>
  );
}

export default function SettingsPage() {
  return (
    <AuthGate>
      <SettingsInner />
    </AuthGate>
  );
}
