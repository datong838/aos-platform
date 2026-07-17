import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

/** T3.13 — Chatbot Studio with real tool roundtrip. */
export function StudioPage() {
  const [tools, setTools] = useState<{ id: string; kind: string }[]>([]);
  const [selected, setSelected] = useState<string[]>(["query.objects"]);
  const [query, setQuery] = useState("列出开放工单");
  const [answer, setAnswer] = useState("");
  const [toolCalls, setToolCalls] = useState<unknown[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ items: { id: string; kind: string }[] }>("/v1/aip/tools")
      .then((r) => setTools(r.items))
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  function toggle(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function onChat(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const res = await apiPost<{
        answer: string;
        toolCalls: unknown[];
        route?: string;
        provider?: string;
      }>("/v1/aip/chat", {
        query,
        withTools: selected.length > 0,
        tools: selected,
      });
      setAnswer(
        `${res.answer}\n\n(route=${res.route || "?"} · provider=${res.provider || "?"})`,
      );
      setToolCalls(res.toolCalls || []);
    } catch (ex) {
      setErr(String((ex as Error).message || ex));
    }
  }

  return (
    <PageChrome title="Chatbot Studio" lede="T3.13 · 绑 Tool 真执行 · Facade chat（禁直连厂商）">
      <p className="muted">
        插件目录见 <Link to="/aip/tools">工具面板</Link> ·{" "}
        <Link to="/aip/model-router">模型路由</Link>
      </p>
      <div className="card" style={{ marginBottom: "1rem" }}>
        <strong className="aos-text">绑定 Tools</strong>
        <ul className="card-list">
          {tools.map((t) => (
            <li key={t.id}>
              <label>
                <input
                  type="checkbox"
                  checked={selected.includes(t.id)}
                  onChange={() => toggle(t.id)}
                />{" "}
                {t.kind}:{t.id}
              </label>
            </li>
          ))}
        </ul>
      </div>
      <form className="filter-bar" onSubmit={onChat}>
        <input
          aria-label="studio-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ minWidth: "18rem" }}
        />
        <button type="submit" className="btn">
          试对话（带工具）
        </button>
      </form>
      {err && <p className="error">{err}</p>}
      {answer && <pre className="card">{answer}</pre>}
      {toolCalls.length > 0 && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            Tool 执行结果
          </h2>
          <pre className="card">{JSON.stringify(toolCalls, null, 2)}</pre>
        </>
      )}
    </PageChrome>
  );
}
