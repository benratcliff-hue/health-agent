"use client";

// Ingest observability: is data still flowing? Shows device sync times, per-metric counts
// and recency, meal totals, and last briefing per kind. Read-only, current user's data.

import { useEffect, useState } from "react";

import AuthGate from "../../AuthGate";

const API_BASE = "/api";

type DeviceStatus = {
  kind: string;
  external_id: string | null;
  last_sync_at: string | null;
  created_at: string;
};
type MetricStatus = {
  metric_type: string;
  total: number;
  count_24h: number;
  count_7d: number;
  last_recorded_at: string | null;
};
type BriefingStatus = {
  kind: string;
  last_generated_at: string | null;
  last_delivered_at: string | null;
};
type IngestStatus = {
  now: string;
  total_samples: number;
  last_ingested_at: string | null;
  devices: DeviceStatus[];
  metrics: MetricStatus[];
  meals_total: number;
  last_meal_at: string | null;
  briefings: BriefingStatus[];
};

function fmt(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

function ago(ts: string | null, now: string): string {
  if (!ts) return "never";
  const mins = Math.round((new Date(now).getTime() - new Date(ts).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

const cell: React.CSSProperties = { padding: "4px 8px", borderBottom: "1px solid #eee", textAlign: "left" };

function AdminInner() {
  const [data, setData] = useState<IngestStatus | null>(null);
  const [status, setStatus] = useState("Loading…");

  useEffect(() => {
    fetch(`${API_BASE}/v1/admin/ingest`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((d) => {
        setData(d);
        setStatus("");
      })
      .catch((s) => setStatus(`Error (${s})`));
  }, []);

  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Ingest status</h1>
      <p style={{ color: "#666" }}>
        <a href="/me">Account</a>
      </p>
      {status && <p>{status}</p>}
      {data && (
        <>
          <p style={{ color: "#444" }}>
            <strong>{data.total_samples.toLocaleString()}</strong> metric samples · last
            ingested {ago(data.last_ingested_at, data.now)} · {data.meals_total} meals (last{" "}
            {ago(data.last_meal_at, data.now)})
          </p>

          <h2 style={{ fontSize: 18 }}>Devices</h2>
          {data.devices.length === 0 ? (
            <p style={{ color: "#666" }}>No devices connected.</p>
          ) : (
            <table style={{ borderCollapse: "collapse", width: "100%" }}>
              <thead>
                <tr>
                  <th style={cell}>Kind</th>
                  <th style={cell}>External ID</th>
                  <th style={cell}>Last sync</th>
                </tr>
              </thead>
              <tbody>
                {data.devices.map((d, i) => (
                  <tr key={i}>
                    <td style={cell}>{d.kind}</td>
                    <td style={cell}>{d.external_id ?? "—"}</td>
                    <td style={cell}>
                      {fmt(d.last_sync_at)} ({ago(d.last_sync_at, data.now)})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h2 style={{ fontSize: 18, marginTop: 24 }}>Metrics</h2>
          {data.metrics.length === 0 ? (
            <p style={{ color: "#666" }}>No samples yet.</p>
          ) : (
            <table style={{ borderCollapse: "collapse", width: "100%" }}>
              <thead>
                <tr>
                  <th style={cell}>Metric</th>
                  <th style={cell}>24h</th>
                  <th style={cell}>7d</th>
                  <th style={cell}>Total</th>
                  <th style={cell}>Last sample</th>
                </tr>
              </thead>
              <tbody>
                {data.metrics.map((m) => (
                  <tr key={m.metric_type}>
                    <td style={cell}>{m.metric_type}</td>
                    <td style={cell}>{m.count_24h}</td>
                    <td style={cell}>{m.count_7d}</td>
                    <td style={cell}>{m.total.toLocaleString()}</td>
                    <td style={cell}>{ago(m.last_recorded_at, data.now)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h2 style={{ fontSize: 18, marginTop: 24 }}>Briefings</h2>
          {data.briefings.length === 0 ? (
            <p style={{ color: "#666" }}>None generated yet.</p>
          ) : (
            <table style={{ borderCollapse: "collapse", width: "100%" }}>
              <thead>
                <tr>
                  <th style={cell}>Kind</th>
                  <th style={cell}>Last generated</th>
                  <th style={cell}>Last delivered</th>
                </tr>
              </thead>
              <tbody>
                {data.briefings.map((b) => (
                  <tr key={b.kind}>
                    <td style={cell}>{b.kind}</td>
                    <td style={cell}>{fmt(b.last_generated_at)}</td>
                    <td style={cell}>{fmt(b.last_delivered_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </main>
  );
}

export default function AdminIngestPage() {
  return (
    <AuthGate>
      <AdminInner />
    </AuthGate>
  );
}
