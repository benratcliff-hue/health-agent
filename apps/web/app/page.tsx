// Server component: probes the api's /healthz and /db-ping at request time and renders
// the raw responses. This is the M0 end-to-end proof that web -> api -> Postgres works.

// Force per-request rendering so `next build` does not try to reach the api at build
// time (it would not be running in CI). In Next 16 fetch is uncached by default, but
// being explicit keeps the intent obvious.
export const dynamic = "force-dynamic";

// This is a Server Component, so it calls the backend directly (server-to-server) rather
// than through the browser /api proxy.
const API_BASE = process.env.API_ORIGIN ?? "http://localhost:8000";

type ProbeResult = {
  ok: boolean;
  status: number;
  body: unknown;
};

async function probe(path: string): Promise<ProbeResult> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    const body = await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, body };
  } catch (err) {
    // The api being down is an expected state to display, not a crash.
    return { ok: false, status: 0, body: { error: String(err) } };
  }
}

function ProbeCard({ name, path, result }: { name: string; path: string; result: ProbeResult }) {
  return (
    <section style={{ border: "1px solid #ccc", borderRadius: 8, padding: 16, marginBottom: 16 }}>
      <h2 style={{ margin: "0 0 8px" }}>
        {result.ok ? "✅" : "❌"} {name}{" "}
        <code style={{ fontWeight: "normal", color: "#666" }}>
          {path} ({result.status || "no response"})
        </code>
      </h2>
      <pre style={{ margin: 0, overflowX: "auto" }}>{JSON.stringify(result.body, null, 2)}</pre>
    </section>
  );
}

export default async function Home() {
  const [health, dbPing] = await Promise.all([probe("/healthz"), probe("/db-ping")]);

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Personal Health Agent</h1>
      <p style={{ color: "#666" }}>
        M0 status page. Probing the api at <code>{API_BASE}</code>.
      </p>
      <ProbeCard name="API liveness" path="/healthz" result={health} />
      <ProbeCard name="Database" path="/db-ping" result={dbPing} />
      <nav style={{ marginTop: 8 }}>
        <a href="/login">Sign in</a> · <a href="/me">Account</a>
      </nav>
    </main>
  );
}
