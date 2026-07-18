import { useEffect, useState, type ReactNode } from "react";
import { apiGet, apiPost } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";
import { BpDebugPanel } from "./blueprintUi";

export function JsonBlock({ value }: { value: unknown }) {
  return <BpDebugPanel value={value} title="完整 JSON" />;
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

export { apiGet, apiPost };
