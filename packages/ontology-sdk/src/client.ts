/** T-SDK.1 / 146 — thin Ontology + Draft client for aos-api only. */

export type OntologyClientOptions = {
  baseUrl: string;
  /** Bearer access token (no "Bearer " prefix required). */
  token: string;
  orgId: string;
  projectId: string;
  fetchImpl?: typeof fetch;
};

export type ApiErrorBody = {
  code?: string;
  message?: string;
  traceId?: string;
};

export class OntologyApiError extends Error {
  status: number;
  body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody, fallback: string) {
    super(body.message || fallback);
    this.name = "OntologyApiError";
    this.status = status;
    this.body = body;
  }
}

export type ObjectRow = {
  id?: string;
  objectType?: string;
  properties?: Record<string, unknown>;
  [key: string]: unknown;
};

export type DraftRow = {
  id?: string;
  status?: string;
  objectType?: string;
  objectId?: string;
  title?: string;
  [key: string]: unknown;
};

export type ObjectQuery = {
  branch?: string;
};

function joinUrl(base: string, path: string): string {
  const b = base.replace(/\/+$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${b}${p}`;
}

function withQuery(path: string, query?: ObjectQuery): string {
  if (!query?.branch) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}branch=${encodeURIComponent(query.branch)}`;
}

export function createOntologyClient(opts: OntologyClientOptions) {
  const fetchImpl = opts.fetchImpl ?? fetch;
  const baseUrl = opts.baseUrl;

  function headers(): HeadersInit {
    const tok = opts.token.startsWith("Bearer ")
      ? opts.token
      : `Bearer ${opts.token}`;
    return {
      Authorization: tok,
      "Content-Type": "application/json",
      "X-Org-Id": opts.orgId,
      "X-Project-Id": opts.projectId,
    };
  }

  async function request<T>(
    method: string,
    path: string,
    body?: unknown,
    extraHeaders?: Record<string, string>,
  ): Promise<T> {
    const url = joinUrl(baseUrl, path);
    // Safe log: org/project only — never token
    console.info("[ontology-sdk]", {
      method,
      path,
      org_id: opts.orgId,
      project_id: opts.projectId,
    });
    const res = await fetchImpl(url, {
      method,
      headers: { ...headers(), ...(extraHeaders || {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) {
      const errBody = (await res.json().catch(() => ({}))) as ApiErrorBody;
      throw new OntologyApiError(res.status, errBody, `HTTP ${res.status}`);
    }
    if (res.status === 204) {
      return undefined as T;
    }
    return (await res.json()) as T;
  }

  return {
    listObjects(objectType: string, query?: ObjectQuery): Promise<{ items: ObjectRow[] }> {
      return request(
        "GET",
        withQuery(`/v1/objects/${encodeURIComponent(objectType)}`, query),
      );
    },

    getObject(
      objectType: string,
      objectId: string,
      query?: ObjectQuery,
    ): Promise<ObjectRow> {
      return request(
        "GET",
        withQuery(
          `/v1/objects/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}`,
          query,
        ),
      );
    },

    putObject(
      objectType: string,
      objectId: string,
      body: Record<string, unknown>,
      query?: ObjectQuery,
    ): Promise<ObjectRow | Record<string, unknown>> {
      return request(
        "PUT",
        withQuery(
          `/v1/objects/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}`,
          query,
        ),
        body,
      );
    },

    neighbors(
      objectType: string,
      objectId: string,
    ): Promise<{ items?: unknown[]; neighbors?: unknown[]; engine?: string } | Record<string, unknown>> {
      return request(
        "GET",
        `/v1/objects/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}/neighbors`,
      );
    },

    listDrafts(): Promise<{ items: DraftRow[] }> {
      return request("GET", "/v1/aip/drafts");
    },

    createDraft(body: Record<string, unknown>): Promise<DraftRow> {
      return request("POST", "/v1/aip/drafts", body);
    },

    approveDraft(
      draftId: string,
      optsApprove?: { idempotencyKey?: string; allowConflicts?: boolean },
    ): Promise<Record<string, unknown>> {
      const extra: Record<string, string> = {};
      if (optsApprove?.idempotencyKey) {
        extra["Idempotency-Key"] = optsApprove.idempotencyKey;
      }
      if (optsApprove?.allowConflicts) {
        extra["X-Allow-Conflicts"] = "true";
      }
      return request(
        "POST",
        `/v1/aip/drafts/${encodeURIComponent(draftId)}/approve`,
        {},
        extra,
      );
    },

    rejectDraft(draftId: string, body: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
      return request(
        "POST",
        `/v1/aip/drafts/${encodeURIComponent(draftId)}/reject`,
        body,
      );
    },
  };
}

export type OntologyClient = ReturnType<typeof createOntologyClient>;
