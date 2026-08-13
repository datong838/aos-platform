// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({
  listBriefs: vi.fn(), listBundles: vi.fn(), listEvalContracts: vi.fn(), listResponsibilityPlans: vi.fn(),
  freezeBrief: vi.fn(), freezeEvalContract: vi.fn(), freezeResponsibilityPlan: vi.fn(),
}));
vi.mock("../../api/aipProductionContracts", () => ({ aipProductionContracts: sdk }));
import { ProductionContractsPage } from "./ProductionContractsPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const tenant={orgId:"org-org",projectId:"dev-project"},hash="a".repeat(64),exact=(resourceType:string,resourceId:string)=>({resourceType,resourceId,revision:1,contentHash:hash});
describe("ProductionContractsPage W2-B authority state",()=>{
  let host:HTMLDivElement,root:Root;
  beforeEach(()=>{host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);Object.values(sdk).forEach(mock=>mock.mockReset());sdk.listBriefs.mockResolvedValue({tenant,items:[],count:0});sdk.listBundles.mockResolvedValue({tenant,items:[],count:0});sdk.listResponsibilityPlans.mockResolvedValue({tenant,items:[],count:0});});
  afterEach(()=>{act(()=>root.unmount());host.remove();});
  it("展示四类权威空态且不伪造 ResponsibilityTemplate",async()=>{sdk.listEvalContracts.mockResolvedValue({tenant,items:[],count:0});await act(async()=>root.render(<ProductionContractsPage/>));await act(async()=>undefined);expect(host.textContent).toContain("0 Responsibility");expect(host.textContent).toContain("ResponsibilityTemplateRevision 权威未接入前保持 fail-closed");});
  it("阻断的 Eval 显示原因并禁止冻结",async()=>{sdk.listEvalContracts.mockResolvedValue({tenant,count:1,items:[{tenant,contractId:"eval-1",revision:1,version:1,suiteRef:exact("EvalSuiteRevision","suite-1"),publicationRef:null,releaseGateRef:null,artifactSchemaRef:{resourceType:"Schema",resourceId:"artifact",revision:"1",authority:"aip"},severityThresholds:{critical:0.9},gatePolicy:{},returnMapping:{fail:"review"},overridePolicy:{},contentHash:hash,lifecycle:"draft",readiness:"blocked",blockers:[{code:"PUBLICATION_REF_REQUIRED",message:"缺少发布事实",resourceRef:null}],createdBy:"user:dev",createdAt:"2026-08-14T00:00:00Z"}]});await act(async()=>root.render(<ProductionContractsPage/>));await act(async()=>undefined);expect(host.textContent).toContain("PUBLICATION_REF_REQUIRED");const button=[...host.querySelectorAll("button")].find(item=>item.textContent==="冻结 Eval") as HTMLButtonElement;expect(button.disabled).toBe(true);expect(sdk.freezeEvalContract).not.toHaveBeenCalled();});
});
