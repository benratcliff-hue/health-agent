"use client";

// Chat coach UI. POSTs to the api (same-origin /api proxy, so the session cookie is sent)
// and reads the SSE stream, appending text deltas to the current assistant message.

import { useRef, useState } from "react";

const API_BASE = "/api";

type Turn = { role: "user" | "assistant"; content: string };

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const conversationId = useRef<string | null>(null);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    setTurns((t) => [...t, { role: "user", content: message }, { role: "assistant", content: "" }]);

    try {
      const res = await fetch(`${API_BASE}/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message, conversation_id: conversationId.current }),
      });
      if (!res.ok || !res.body) throw new Error(`chat failed (${res.status})`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) >= 0) {
          const line = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.conversation_id) conversationId.current = data.conversation_id;
          if (data.text) {
            setTurns((t) => {
              const copy = [...t];
              copy[copy.length - 1] = {
                role: "assistant",
                content: copy[copy.length - 1].content + data.text,
              };
              return copy;
            });
          }
          if (data.error) {
            setTurns((t) => {
              const copy = [...t];
              copy[copy.length - 1] = { role: "assistant", content: `[error: ${data.error}]` };
              return copy;
            });
          }
        }
      }
    } catch (err) {
      setTurns((t) => [...t.slice(0, -1), { role: "assistant", content: `[error: ${err}]` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: 24, fontFamily: "system-ui" }}>
      <h1>Coach</h1>
      <p style={{ color: "#666" }}>
        <a href="/me">Account</a>
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, margin: "16px 0" }}>
        {turns.map((t, i) => (
          <div
            key={i}
            style={{
              alignSelf: t.role === "user" ? "flex-end" : "flex-start",
              background: t.role === "user" ? "#e8f0fe" : "#f1f1f1",
              borderRadius: 8,
              padding: "8px 12px",
              maxWidth: "80%",
              whiteSpace: "pre-wrap",
            }}
          >
            {t.content || (busy && i === turns.length - 1 ? "…" : "")}
          </div>
        ))}
      </div>
      <form onSubmit={send} style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your coach…"
          style={{ flex: 1, padding: 8 }}
        />
        <button type="submit" disabled={busy} style={{ padding: "8px 16px" }}>
          Send
        </button>
      </form>
    </main>
  );
}
