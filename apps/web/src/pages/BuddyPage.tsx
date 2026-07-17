import { useState, type FormEvent } from "react";
import { apiPost } from "../api/client";
import type { SelectionFilter } from "../selection";

/** T1.12 — Buddy shell with Selection chips; chat via /v1/buddy/ask Mock. */
export function BuddyPage({
  initialSelection = [{ field: "site", value: "DC-East" }],
}: {
  initialSelection?: SelectionFilter[];
}) {
  const [selection] = useState<SelectionFilter[]>(initialSelection);
  const [query, setQuery] = useState("当前工单风险？");
  const [answer, setAnswer] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function onAsk(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await apiPost<{ answer: string; traceId: string }>(
        "/v1/buddy/ask",
        {
          query,
          context: {
            selection,
            objectType: "WorkOrder",
            objectId: "wo-1001",
            demoStory: "workorder-local-demo",
          },
        },
      );
      setAnswer(`${res.answer} · trace=${res.traceId}`);
    } catch (err) {
      setError(String((err as Error).message || err));
    }
  }

  return (
    <section>
      <h1>Buddy · 智能助手</h1>
      <p className="muted">
        TB.6 · Context = Selection + WorkOrder/wo-1001 · `/v1/buddy/ask` → Facade
      </p>
      <div className="chips">
        {selection.map((s) => (
          <span key={`${s.field}:${s.value}`} className="chip">
            {s.field}={s.value}
          </span>
        ))}
      </div>
      <form className="filter-bar" onSubmit={onAsk}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="buddy-query"
          style={{ flex: 1, minWidth: 200 }}
        />
        <button type="submit">询问</button>
      </form>
      {error && <p className="error">{error}</p>}
      {answer && <div className="card">{answer}</div>}
    </section>
  );
}
