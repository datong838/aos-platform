/**
 * 149 · Ontology SDK React hooks（替代 objects/drafts 的 useJsonGet）
 */
import { useCallback, useEffect, useState } from "react";
import { getOntologyClient } from "./ontologyClient";
import type { DraftRow, ObjectRow } from "@aos/ontology-sdk";

export function useOntologyObject(objectType: string, objectId: string) {
  const [data, setData] = useState<ObjectRow | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    if (!objectType || !objectId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr(null);
    getOntologyClient()
      .getObject(objectType, objectId)
      .then(setData)
      .catch((e) => setErr(String((e as Error).message || e)))
      .finally(() => setLoading(false));
  }, [objectType, objectId]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, err, loading, reload, setData, setErr };
}

export function useOntologyDrafts() {
  const [data, setData] = useState<{ items: DraftRow[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    setErr(null);
    getOntologyClient()
      .listDrafts()
      .then((res) => setData({ items: res.items || [] }))
      .catch((e) => setErr(String((e as Error).message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, err, loading, reload, setData, setErr };
}
