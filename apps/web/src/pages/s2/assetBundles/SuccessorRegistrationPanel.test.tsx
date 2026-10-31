import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SuccessorRegistrationPanel } from "./SuccessorRegistrationPanel";
import { assetControlClient } from "../../../api/assetControl/client";
import { getTenant, setTenant } from "../../../api/tenant";
import type { IdempotencyKey } from "../../../api/assetControl/idempotency";
import type { SuccessorPreparation } from "../../../api/assetControl/successorRegistration";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const id = "11111111-1111-4111-8111-111111111111", hash = `sha256:${"1".repeat(64)}` as const;
const original = { ...getTenant() };
function prepared(key: IdempotencyKey): SuccessorPreparation {
  return { schemaVersion: "aos.ecommerce.successor-preparation/v1", tenant: { orgId: "org-org", projectId: "dev-project" },
    installationId: id, ready: true, reasons: [], executable: false, options: [{ label: "接续原安装的经营任务", command: {
      schemaVersion: "aos.ecommerce.successor-dispatch-registration/v1", expectedGroupRevision: 367,
      predecessorDetachReceiptRef: { resourceType: "DispatchDisableDetachReceipt", resourceId: "55555555-5555-4555-8555-555555555555", revision: 1, contentHash: hash },
      registration: { schemaVersion: "aos.ecommerce.first-dispatch-registration/v1",
        installationRef: { installationId: id, revision: 5, lockHash: hash, overlayRevision: "overlay-1" },
        generation: "22222222-2222-4222-8222-222222222222", bindingRevision: 4, executionEpoch: 3,
        configRef: { configurationId: "33333333-3333-4333-8333-333333333333", revision: 1, hash },
        groupId: "44444444-4444-4444-8444-444444444444", idempotencyKey: key } } }] };
}
let host: HTMLDivElement, root: Root;
const onRegistered = vi.fn();
beforeEach(() => {
  sessionStorage.clear(); setTenant({ orgId: "org-org", projectId: "dev-project", subject: "signed-user", roles: ["admin"] });
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); onRegistered.mockReset();
  vi.spyOn(assetControlClient, "getSuccessorPreparation").mockImplementation(async (_id, key) => prepared(key));
  vi.spyOn(assetControlClient, "createSuccessorRegistration").mockResolvedValue({ resourceType: "SuccessorDispatchRegistrationReceipt", resourceId: id, revision: 1, contentHash: hash });
  vi.spyOn(assetControlClient, "readSuccessorRegistration").mockResolvedValue({ resourceType: "SuccessorDispatchRegistrationReceipt", resourceId: id, revision: 1, contentHash: hash });
});
afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); sessionStorage.clear(); setTenant(original); });
async function render(disabled = false) {
  await act(async () => root.render(<SuccessorRegistrationPanel installationId={id} allowedPrepare disabled={disabled} onRegistered={onRegistered} />));
}
async function click(label: string) {
  const b = Array.from(host.querySelectorAll("button")).find(b => b.textContent === label);
  expect(b).toBeDefined(); await act(async () => b!.click());
}
it("prepares on request and confirms in business language without internal fields", async () => {
  await render(); expect(assetControlClient.getSuccessorPreparation).not.toHaveBeenCalled();
  await click("核对接续条件");
  expect(assetControlClient.createSuccessorRegistration).not.toHaveBeenCalled();
  expect(host.textContent).toContain("接续原安装的经营任务");
  expect(host.textContent).not.toContain(id); expect(host.querySelectorAll("input,textarea")).toHaveLength(0);
  await click("确认接续登记");
  expect(assetControlClient.createSuccessorRegistration).toHaveBeenCalledTimes(1);
  expect(host.textContent).toContain("尚未启动业务"); expect(onRegistered).toHaveBeenCalledTimes(1);
});
it("shows missing business conditions without a submit action", async () => {
  vi.mocked(assetControlClient.getSuccessorPreparation).mockImplementation(async (_id, key) => ({ ...prepared(key), ready: false, reasons: ["新安装尚未完成运行配置"], options: [] }));
  await render(); await click("核对接续条件");
  expect(host.textContent).toContain("新安装尚未完成运行配置"); expect(host.textContent).not.toContain("确认接续登记");
});
it("retains an unknown request and only reads the same command", async () => {
  vi.mocked(assetControlClient.createSuccessorRegistration).mockRejectedValueOnce(new Error("unconfirmed"));
  await render(); await click("核对接续条件"); await click("确认接续登记");
  const sent = vi.mocked(assetControlClient.createSuccessorRegistration).mock.calls[0][0];
  expect(host.textContent).not.toContain("确认接续登记"); await click("查看原登记结果");
  expect(assetControlClient.createSuccessorRegistration).toHaveBeenCalledTimes(1);
  expect(vi.mocked(assetControlClient.readSuccessorRegistration).mock.calls[0][0]).toEqual(sent);
});
it("restores a possibly attempted command after remount without a new POST choice", async () => {
  vi.mocked(assetControlClient.createSuccessorRegistration).mockRejectedValueOnce(new Error("unknown"));
  await render(); await click("核对接续条件"); await click("确认接续登记");
  await act(async () => { root.unmount(); root = createRoot(host); }); await render();
  expect(host.textContent).not.toContain("确认接续登记"); expect(host.textContent).not.toContain("核对接续条件");
  await click("查看原登记结果"); expect(assetControlClient.createSuccessorRegistration).toHaveBeenCalledTimes(1);
});
it("does not repeat a POST on double click", async () => {
  await render(); await click("核对接续条件");
  const b = Array.from(host.querySelectorAll("button")).find(b => b.textContent === "确认接续登记")!;
  await act(async () => { b.click(); b.click(); }); expect(assetControlClient.createSuccessorRegistration).toHaveBeenCalledTimes(1);
});
it("does not post if original intent cannot be saved", async () => {
  await render(); await click("核对接续条件");
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage unavailable"); });
  await click("确认接续登记"); expect(assetControlClient.createSuccessorRegistration).not.toHaveBeenCalled();
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
});
it("preserves a slot when receipt binding fails, and 404 never resends", async () => {
  vi.mocked(assetControlClient.createSuccessorRegistration).mockRejectedValueOnce(new Error("receipt mismatch"));
  vi.mocked(assetControlClient.readSuccessorRegistration).mockRejectedValueOnce(new Error("404"));
  await render(); await click("核对接续条件"); await click("确认接续登记");
  const keys = Object.keys(sessionStorage); expect(keys.some(k => k.startsWith("aos-successor-intent:"))).toBe(true);
  await click("查看原登记结果"); expect(host.textContent).not.toContain("确认接续登记");
  expect(assetControlClient.createSuccessorRegistration).toHaveBeenCalledTimes(1);
  expect(Object.keys(sessionStorage).filter(k => k.startsWith("aos-successor-intent:"))).toHaveLength(1);
});
it("invalidates a late preparation on identity change", async () => {
  let finish!: (r: SuccessorPreparation) => void;
  const key = "pending-test" as IdempotencyKey;
  vi.mocked(assetControlClient.getSuccessorPreparation).mockImplementationOnce(() => new Promise(r => { finish = r; }));
  await render(); await click("核对接续条件");
  await act(async () => setTenant({ subject: "another-user" }));
  await act(async () => finish(prepared(key)));
  expect(host.textContent).not.toContain("确认接续登记"); expect(assetControlClient.createSuccessorRegistration).not.toHaveBeenCalled();
});
it("disables operations while offline or parent is busy", async () => {
  await render(true); expect(host.querySelector("button")!.disabled).toBe(true);
});

it.each(["saved-before-send", "corrupt", "foreign-owner"])("freezes recovered %s records", async kind => {
  const owner = { orgId: "org-org", projectId: "dev-project", subject: "signed-user", installationId: id };
  const record = { schemaVersion: "aos.successor-registration.intent/v1", owner: { ...owner },
    command: prepared("saved-before-send" as IdempotencyKey).options[0].command };
  if (kind === "foreign-owner") record.owner.subject = "different-user";
  sessionStorage.setItem(`aos-successor-intent:${JSON.stringify(owner)}`, kind === "corrupt" ? "{" : JSON.stringify(record));
  await render();
  expect(host.textContent).not.toContain("确认接续登记");
  expect(assetControlClient.getSuccessorPreparation).not.toHaveBeenCalled();
  expect(assetControlClient.createSuccessorRegistration).not.toHaveBeenCalled();
  if (kind === "saved-before-send") expect(host.textContent).toContain("查看原登记结果");
  else { expect(host.querySelector('[role="alert"]')).not.toBeNull(); expect(host.querySelector("button")!.disabled).toBe(true); }
});
