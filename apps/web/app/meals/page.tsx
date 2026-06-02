"use client";

// Meal log: upload a photo (session-authed) and see recent meals.
// M1 stores the photo + a row; calorie/macro estimates land in M2.

import { useEffect, useRef, useState } from "react";

import AuthGate from "../AuthGate";

const API_BASE = "/api";

type Meal = {
  id: string;
  photo_url: string;
  eaten_at: string;
  note: string | null;
  kcal_est: number | null;
  source: string;
};

function MealsInner() {
  const [meals, setMeals] = useState<Meal[]>([]);
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    const res = await fetch(`${API_BASE}/v1/meals`, { credentials: "include" });
    if (res.ok) setMeals(await res.json());
  }

  useEffect(() => {
    fetch(`${API_BASE}/v1/meals`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setMeals(data))
      .catch(() => {});
  }, []);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setStatus("Pick a photo first.");
      return;
    }
    setBusy(true);
    setStatus("Uploading…");
    const form = new FormData();
    form.append("file", file);
    if (note) form.append("note", note);
    try {
      const res = await fetch(`${API_BASE}/v1/meals`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      if (res.ok) {
        setStatus("Logged.");
        setNote("");
        if (fileRef.current) fileRef.current.value = "";
        await load();
      } else {
        setStatus(`Error (${res.status})`);
      }
    } catch {
      setStatus("Error (request failed)");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Meals</h1>
      <p style={{ color: "#666" }}>
        <a href="/me">Account</a>
      </p>
      <form onSubmit={upload} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <input ref={fileRef} type="file" accept="image/*" capture="environment" />
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (optional), e.g. chicken & rice"
          style={{ padding: 8 }}
        />
        <div>
          <button type="submit" disabled={busy} style={{ padding: "8px 16px" }}>
            Log meal
          </button>{" "}
          <span style={{ color: "#666" }}>{status}</span>
        </div>
      </form>

      <h2 style={{ fontSize: 18, marginTop: 24 }}>Recent</h2>
      {meals.length === 0 && <p style={{ color: "#666" }}>No meals logged yet.</p>}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
          gap: 12,
        }}
      >
        {meals.map((m) => (
          <figure key={m.id} style={{ margin: 0 }}>
            {/* Presigned R2 URL; plain img is fine for a private 2-person app. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={m.photo_url}
              alt={m.note ?? "meal"}
              style={{ width: "100%", height: 160, objectFit: "cover", borderRadius: 8 }}
            />
            <figcaption style={{ fontSize: 12, color: "#444" }}>
              {new Date(m.eaten_at).toLocaleString()}
              {m.note ? ` — ${m.note}` : ""}
            </figcaption>
          </figure>
        ))}
      </div>
    </main>
  );
}

export default function MealsPage() {
  return (
    <AuthGate>
      <MealsInner />
    </AuthGate>
  );
}
