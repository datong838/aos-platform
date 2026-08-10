export const AIP_OPERATIONS = {
  listCapabilities: { method: "GET", path: "/v1/aip/capabilities", mutation: false },
  tripCircuit: { method: "POST", path: "/v1/aip/circuit/trip", mutation: true },
  listDrafts: { method: "GET", path: "/v1/aip/drafts", mutation: false },
  getDraft: { method: "GET", path: "/v1/aip/drafts/{draft_id}", mutation: false },
  approveDraft: { method: "POST", path: "/v1/aip/drafts/{draft_id}/approve", mutation: true },
  rejectDraft: { method: "POST", path: "/v1/aip/drafts/{draft_id}/reject", mutation: true },
  listEvals: { method: "GET", path: "/v1/aip/evals", mutation: false },
  listInsights: { method: "GET", path: "/v1/aip/insights", mutation: false },
  listTools: { method: "GET", path: "/v1/aip/tools", mutation: false },
} as const;

export type AipOperationId = keyof typeof AIP_OPERATIONS;

