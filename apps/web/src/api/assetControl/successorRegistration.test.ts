import { afterEach, expect, it, vi } from "vitest";
import { AssetControlClient } from "./client";
import { setConnectivity } from "../../lib/offlineStore";
import type { IdempotencyKey } from "./idempotency";
import type { SuccessorRegistrationCommand } from "./successorRegistration";

const id = "11111111-1111-4111-8111-111111111111";
const hash = `sha256:${"1".repeat(64)}` as const;
function command(): SuccessorRegistrationCommand {
  return { schemaVersion: "aos.ecommerce.successor-dispatch-registration/v1",
    registration: { schemaVersion: "aos.ecommerce.first-dispatch-registration/v1",
      installationRef: { installationId: id, revision: 5, lockHash: hash, overlayRevision: "overlay-1" },
      generation: "22222222-2222-4222-8222-222222222222", bindingRevision: 4, executionEpoch: 3,
      configRef: { configurationId: "33333333-3333-4333-8333-333333333333", revision: 1, hash },
      groupId: "44444444-4444-4444-8444-444444444444", idempotencyKey: "successor-1" as IdempotencyKey },
    expectedGroupRevision: 367, predecessorDetachReceiptRef: { resourceType: "DispatchDisableDetachReceipt",
      resourceId: "55555555-5555-4555-8555-555555555555", revision: 1, contentHash: hash } };
}
function receipt(c = command()) {
  return { schemaVersion: "aos.ecommerce.successor-dispatch-registration-receipt/v1",
    tenant: { orgId: "org-org", projectId: "dev-project" }, receiptId: "66666666-6666-4666-8666-666666666666",
    installationId: id, generation: c.registration.generation, groupId: c.registration.groupId,
    requestHash: hash, idempotencyKey: c.registration.idempotencyKey, actor: "signed-user",
    request: structuredClone(c), dispatchSnapshot: [], executable: false,
    createdAt: "2026-10-31T05:00:00+00:00", contentHash: hash, replayed: false };
}
function harness(value: unknown = receipt()) {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(value), { status: 201 }));
  const auth = { Authorization: "Bearer test-token", "X-Org-Id": "org-org", "X-Project-Id": "dev-project" };
  const client = new AssetControlClient({ fetch, getBaseUrl: () => "http://test", getAuthHeaders: () => auth });
  return { client, fetch, auth };
}
afterEach(() => setConnectivity("unknown", "successor-test-cleanup"));

it("submits original exact command once with identity, version and stable key", async () => {
  const { client, fetch } = harness();
  const result = await client.createSuccessorRegistration(command());
  expect(result).toEqual({ resourceType: "SuccessorDispatchRegistrationReceipt", resourceId: receipt().receiptId, revision: 1, contentHash: hash });
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe(`http://test/v1/bundle-runtime-installations/${id}/ecommerce-growth-successor-registrations`);
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body)).toEqual(command());
  expect(init.headers.get("If-Match")).toBe('"5"');
  expect(init.headers.get("Idempotency-Key")).toBe("successor-1");
  expect(init.headers.get("Authorization")).toBe("Bearer test-token");
});

it("queries the original receipt with only its key and requires historical evidence", async () => {
  const { client, fetch } = harness({ ...receipt(), historical: true });
  await client.readSuccessorRegistration(command());
  const [url, init] = fetch.mock.calls[0];
  expect(url).toMatch(/ecommerce-growth-successor-registrations\/receipt$/);
  expect(init.method).toBe("GET");
  expect(init.headers.get("Idempotency-Key")).toBe("successor-1");
  expect(init.headers.has("If-Match")).toBe(false);
  expect(init.body).toBeUndefined();
});

it.each(["tenant", "installation", "generation", "key", "request", "executable"])("rejects %s receipt drift", async defect => {
  const r = receipt();
  if (defect === "tenant") r.tenant.orgId = "foreign-org";
  if (defect === "installation") r.installationId = r.generation;
  if (defect === "generation") r.generation = id;
  if (defect === "key") r.idempotencyKey = "foreign" as IdempotencyKey;
  if (defect === "request") r.request.predecessorDetachReceiptRef.contentHash = `sha256:${"2".repeat(64)}`;
  if (defect === "executable") r.executable = true;
  const { client, fetch } = harness(r);
  await expect(client.createSuccessorRegistration(command())).rejects.toThrow();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("requires historical=true on readback", async () => {
  await expect(harness().client.readSuccessorRegistration(command())).rejects.toThrow();
});

it("accepts identical native JSON with different object key ordering", async () => {
  const r = receipt();
  r.request.registration.installationRef = Object.fromEntries(Object.entries(r.request.registration.installationRef).reverse()) as typeof r.request.registration.installationRef;
  r.request.registration.configRef = Object.fromEntries(Object.entries(r.request.registration.configRef).reverse()) as typeof r.request.registration.configRef;
  r.request.predecessorDetachReceiptRef = Object.fromEntries(Object.entries(r.request.predecessorDetachReceiptRef).reverse()) as typeof r.request.predecessorDetachReceiptRef;
  await expect(harness(r).client.createSuccessorRegistration(command())).resolves.toHaveProperty("resourceType", "SuccessorDispatchRegistrationReceipt");
});

it("keeps sent command and tenant snapshots when caller objects change in flight", async () => {
  const c = command(), original = structuredClone(c), { client, fetch, auth } = harness();
  let resolve!: (r: Response) => void;
  fetch.mockImplementationOnce(() => new Promise<Response>(r => { resolve = r; }));
  const pending = client.createSuccessorRegistration(c);
  c.registration.installationRef.revision = 99; auth["X-Org-Id"] = "different";
  resolve(new Response(JSON.stringify(receipt(original)), { status: 201 }));
  await expect(pending).resolves.toHaveProperty("resourceType", "SuccessorDispatchRegistrationReceipt");
});

it.each(["extra", "negative", "detach", "uuid"])("refuses invalid %s command before sending", async defect => {
  const c = command();
  if (defect === "extra") Object.assign(c, { actor: "private-sentinel" });
  if (defect === "negative") c.registration.bindingRevision = -1;
  if (defect === "detach") Object.assign(c.predecessorDetachReceiptRef, { resourceType: "Approval" });
  if (defect === "uuid") c.registration.installationRef.installationId = "not-a-uuid";
  const { client, fetch } = harness();
  await expect(Promise.resolve().then(() => client.createSuccessorRegistration(c))).rejects.toThrow();
  expect(fetch).not.toHaveBeenCalled();
});

it("refuses offline writes", async () => {
  setConnectivity("offline", "successor-test");
  const { client, fetch } = harness();
  await expect(Promise.resolve().then(() => client.createSuccessorRegistration(command()))).rejects.toThrow();
  expect(fetch).not.toHaveBeenCalled();
});

it("never retries an unknown network result", async () => {
  const { client, fetch } = harness(); fetch.mockRejectedValueOnce(new TypeError("disconnect"));
  await expect(client.createSuccessorRegistration(command())).rejects.toThrow();
  expect(fetch).toHaveBeenCalledTimes(1);
});

function preparation() {
  return { schemaVersion: "aos.ecommerce.successor-preparation/v1", tenant: { orgId: "org-org", projectId: "dev-project" },
    installationId: id, ready: true, reasons: [], options: [{ label: "接续原安装的经营任务", command: command() }], executable: false };
}

it("loads server-owned preparation with the original key, no version or POST", async () => {
  const { client, fetch } = harness(preparation());
  const result = await client.getSuccessorPreparation(id, command().registration.idempotencyKey);
  expect(result.options[0].command).toEqual(command());
  const [url, init] = fetch.mock.calls[0];
  expect(url).toMatch(/ecommerce-growth-successor-registration-preparation$/);
  expect(init.method).toBe("GET");
  expect(init.headers.get("Idempotency-Key")).toBe("successor-1");
  expect(init.headers.has("If-Match")).toBe(false);
});

it.each(["tenant", "installation", "key", "state", "execution"])("rejects preparation %s mismatch", async defect => {
  const r = preparation();
  if (defect === "tenant") r.tenant.orgId = "foreign";
  if (defect === "installation") r.installationId = command().registration.generation;
  if (defect === "key") r.options[0].command.registration.idempotencyKey = "other" as IdempotencyKey;
  if (defect === "state") r.ready = false;
  if (defect === "execution") r.executable = true;
  await expect(harness(r).client.getSuccessorPreparation(id, command().registration.idempotencyKey)).rejects.toThrow();
});
