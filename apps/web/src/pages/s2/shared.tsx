import { useEffect, useState, type ReactNode } from "react";
import { apiGet, apiPost } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";

export function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="card" style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export function useJsonGet<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(path));

  function reload() {
    if (!path) return;
    setLoading(true);
    setErr(null);
    apiGet<T>(path)
      .then(setData)
      .catch((e) => setErr(String((e as Error).message || e)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- path-keyed
  }, [path]);

  return { data, err, loading, reload, setData, setErr };
}

export function S2Chrome({
  title,
  lede,
  children,
}: {
  title: string;
  lede: string;
  children: ReactNode;
}) {
  return (
    <PageChrome title={title} lede={`S2 MVP · ${lede}`}>
      {children}
    </PageChrome>
  );
}

export function ItemsPage({
  title,
  lede,
  path,
}: {
  title: string;
  lede: string;
  path: string;
}) {
  const { data, err, loading, reload } = useJsonGet<{ items: unknown[] }>(path);
  return (
    <S2Chrome title={title} lede={lede}>
      <button type="button" className="btn" onClick={() => reload()}>
        刷新
      </button>
      {loading && <p className="muted">加载中…</p>}
      {err && <p className="error">{err}</p>}
      {data && (
        <>
          <p className="muted">共 {data.items?.length ?? 0} 条</p>
          <JsonBlock value={data.items} />
        </>
      )}
    </S2Chrome>
  );
}

export { apiGet, apiPost };
