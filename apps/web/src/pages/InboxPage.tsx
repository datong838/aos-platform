import { useEffect, useState, type FormEvent } from "react";
import { apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import {
  addFilter,
  canAddFilter,
  SELECTION_LIMIT,
  type SelectionFilter,
} from "../selection";
import {
  LargeResultSimulator,
  PaginationGuardBanner,
  useDisplayTotal,
} from "../paginationGuard";

type Row = Record<string, string>;

export function InboxPage() {
  const [filters, setFilters] = useState<SelectionFilter[]>([]);
  const [field, setField] = useState("site");
  const [value, setValue] = useState("DC-East");
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [totalOverride, setTotalOverride] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gateMsg, setGateMsg] = useState<string | null>(null);
  const displayTotal = useDisplayTotal(total, totalOverride);

  async function runQuery(nextFilters: SelectionFilter[]) {
    setError(null);
    setTotalOverride(null);
    try {
      const res = await apiPost<{
        items: Row[];
        total: number;
      }>("/v1/object-sets/query", {
        filters: nextFilters,
        page: 1,
        pageSize: 50,
      });
      setRows(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  useEffect(() => {
    void runQuery([]);
  }, []);

  function onAdd(e: FormEvent) {
    e.preventDefault();
    const next = { field, value };
    const gate = canAddFilter(filters, next);
    if (!gate.ok) {
      setGateMsg(gate.reason);
      return;
    }
    setGateMsg(null);
    try {
      const updated = addFilter(filters, next);
      setFilters(updated);
      void runQuery(updated);
    } catch (err) {
      setGateMsg(String((err as Error).message));
    }
  }

  return (
    <PageChrome
      title="运营台"
      lede={`Selection ${filters.length}/${SELECTION_LIMIT} · 对齐 workshop-module.html`}
    >
      <form className="filter-bar" onSubmit={onAdd}>
        <input
          value={field}
          onChange={(e) => setField(e.target.value)}
          aria-label="field"
        />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-label="value"
        />
        <button type="submit">添加筛选维</button>
        <button
          type="button"
          onClick={() => {
            setFilters([]);
            setGateMsg(null);
            void runQuery([]);
          }}
        >
          清空
        </button>
      </form>
      <LargeResultSimulator onSimulate={(n) => setTotalOverride(n)} />
      <PaginationGuardBanner total={displayTotal} />
      {gateMsg && <p className="error">{gateMsg}</p>}
      {error && <p className="error">{error}</p>}
      <p className="muted">命中 {displayTotal} 条（页内 {rows.length}）</p>
      <table className="data-table">
        <thead>
          <tr>
            <th>id</th>
            <th>title</th>
            <th>status</th>
            <th>site</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.title}</td>
              <td>{r.status}</td>
              <td>{r.site}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </PageChrome>
  );
}
