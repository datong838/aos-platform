// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({
  listBriefs: vi.fn(), listBundles: vi.fn(), listEvalContracts: vi.fn(), listResponsibilityPlans: vi.fn(),
  listStageTemplates: vi.fn(), listArtifactRelations: vi.fn(), listReviewIssues: vi.fn(),
  freezeBrief: vi.fn(), freezeEvalContract: vi.fn(), freezeResponsibilityPlan: vi.fn(),
  freezeStageTemplate: vi.fn(), compileStageTemplate: vi.fn(), resolveReviewIssue: vi.fn(), returnReviewIssue: vi.fn(),
}));
vi.mock("../../api/aipProductionContracts", () => ({ aipProductionContracts: sdk }));
import { ProductionContractsPage } from "./ProductionContractsPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const tenant={orgId:"org-org",projectId:"dev-project"},hash="a".repeat(64),exact=(resourceType:string,resourceId:string)=>({resourceType,resourceId,revision:1,contentHash:hash});
describe("ProductionContractsPage W2-B authority state",()=>{
  let host:HTMLDivElement,root:Root;
  beforeEach(()=>{host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);Object.values(sdk).forEach(mock=>mock.mockReset());sdk.listBriefs.mockResolvedValue({tenant,items:[],count:0});sdk.listBundles.mockResolvedValue({tenant,items:[],count:0});sdk.listResponsibilityPlans.mockResolvedValue({tenant,items:[],count:0});sdk.listStageTemplates.mockResolvedValue({tenant,items:[],count:0});sdk.listArtifactRelations.mockResolvedValue({tenant,items:[],count:0});sdk.listReviewIssues.mockResolvedValue({tenant,items:[],count:0});});
  afterEach(()=>{act(()=>root.unmount());host.remove();});
  it("展示四类权威空态且不伪造 ResponsibilityTemplate",async()=>{sdk.listEvalContracts.mockResolvedValue({tenant,items:[],count:0});await act(async()=>root.render(<ProductionContractsPage/>));await act(async()=>undefined);expect(host.textContent).toContain("0 Responsibility");expect(host.textContent).toContain("ResponsibilityTemplateRevision 权威未接入前保持 fail-closed");});
  it("阻断的 Eval 显示原因并禁止冻结",async()=>{sdk.listEvalContracts.mockResolvedValue({tenant,count:1,items:[{tenant,contractId:"eval-1",revision:1,version:1,suiteRef:exact("EvalSuiteRevision","suite-1"),publicationRef:null,releaseGateRef:null,artifactSchemaRef:{resourceType:"Schema",resourceId:"artifact",revision:"1",authority:"aip"},severityThresholds:{critical:0.9},gatePolicy:{},returnMapping:{fail:"review"},overridePolicy:{},contentHash:hash,lifecycle:"draft",readiness:"blocked",blockers:[{code:"PUBLICATION_REF_REQUIRED",message:"缺少发布事实",resourceRef:null}],createdBy:"user:dev",createdAt:"2026-08-14T00:00:00Z"}]});await act(async()=>root.render(<ProductionContractsPage/>));await act(async()=>undefined);expect(host.textContent).toContain("PUBLICATION_REF_REQUIRED");const button=[...host.querySelectorAll("button")].find(item=>item.textContent==="冻结 Eval") as HTMLButtonElement;expect(button.disabled).toBe(true);expect(sdk.freezeEvalContract).not.toHaveBeenCalled();});
  it("展示 W2-C 三类权威真实空态",async()=>{sdk.listEvalContracts.mockResolvedValue({tenant,items:[],count:0});await act(async()=>root.render(<ProductionContractsPage/>));await act(async()=>undefined);expect(host.textContent).toContain("0 Stage");expect(host.textContent).toContain("尚无 StageTemplate");expect(host.textContent).toContain("尚无 Artifact Relation");expect(host.textContent).toContain("尚无 Review Issue");});
  it("阻断 Stage 显示 source blocker 且不允许冻结或编译",async()=>{sdk.listEvalContracts.mockResolvedValue({tenant,items:[],count:0});sdk.listStageTemplates.mockResolvedValue({tenant,count:1,items:[{tenant,templateId:"stage-1",revision:1,version:1,profile:"ecommerce-standard",sourceBundleRef:exact("AssetBundleRevision","bundle-1"),stages:[{stageId:"analysis",title:"分析",dependsOn:[],applicability:{kind:"always",profiles:[]},requiredSlotIds:["analyst"],inputSchemaRef:{resourceType:"Schema",resourceId:"in",revision:"1",authority:"aip"},outputSchemaRef:{resourceType:"Schema",resourceId:"out",revision:"1",authority:"aip"},gateRefs:[],checkpointPolicy:{},retryPolicy:{},compensationPolicy:{}}],contentHash:hash,lifecycle:"draft",sealedBy:null,sealedAt:null,sealHash:null,readiness:"blocked",blockers:[{code:"STAGE_SOURCE_AUTHORITY_UNAVAILABLE",message:"缺少权威解析器",resourceRef:exact("AssetBundleRevision","bundle-1")}],createdBy:"user:dev",createdAt:"2026-08-14T00:00:00Z"}]});await act(async()=>root.render(<ProductionContractsPage/>));await act(async()=>undefined);expect(host.textContent).toContain("STAGE_SOURCE_AUTHORITY_UNAVAILABLE");const freeze=[...host.querySelectorAll("button")].find(item=>item.textContent==="冻结 Stage") as HTMLButtonElement;expect(freeze.disabled).toBe(true);const compile=[...host.querySelectorAll("button")].find(item=>item.textContent==="编译为 Plan 草稿") as HTMLButtonElement;expect(compile.disabled).toBe(true);});
});
