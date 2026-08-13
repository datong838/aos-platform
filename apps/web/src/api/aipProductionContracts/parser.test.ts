import { describe, expect, it } from "vitest";
import { parseBriefList, parseBundleList, parseEvalContractList, parseResponsibilityPlanList } from "./parser";
const hash="a".repeat(64), tenant={orgId:"org-org",projectId:"dev-project"};
describe("W2-A production contract parser",()=>{
  it("parses exact authority lists",()=>{
    expect(parseBriefList({tenant,count:1,items:[{tenant,briefId:"brief-1",taskId:"task-1",revision:2,version:2,briefType:"ecommerce.analysis",schemaRef:{resourceType:"Schema",resourceId:"analysis",revision:"1",authority:"aip"},spec:{goal:"facts"},contentHash:hash,lifecycle:"frozen",createdBy:"user:dev",createdAt:"2026-08-13T00:00:00Z"}]}).count).toBe(1);
    expect(parseBundleList({tenant,count:0,items:[]}).count).toBe(0);
  });
  it("fails closed on count/hash drift",()=>{
    expect(()=>parseBriefList({tenant,count:1,items:[]})).toThrow("不一致");
    expect(()=>parseBriefList({tenant,count:1,items:[{tenant,briefId:"b",taskId:"t",revision:1,version:1,briefType:"x",schemaRef:{resourceType:"S",resourceId:"s",revision:"1",authority:"a"},spec:{},contentHash:"bad",lifecycle:"draft",createdBy:"u",createdAt:"now"}]})).toThrow("SHA-256");
  });
});
describe("W2-B production contract parser",()=>{
  const exact=(resourceType:string,resourceId:string)=>({resourceType,resourceId,revision:1,contentHash:hash});
  it("parses Eval authority and blocker state",()=>{
    const result=parseEvalContractList({tenant,count:1,items:[{tenant,contractId:"eval-1",revision:1,version:1,suiteRef:exact("EvalSuiteRevision","suite-1"),publicationRef:null,releaseGateRef:null,artifactSchemaRef:{resourceType:"Schema",resourceId:"artifact",revision:"1",authority:"aip"},severityThresholds:{critical:0.9},gatePolicy:{mode:"all"},returnMapping:{fail:"review"},overridePolicy:{allowed:false},contentHash:hash,lifecycle:"draft",readiness:"blocked",blockers:[{code:"PUBLICATION_REF_REQUIRED",message:"缺少发布事实",resourceRef:null}],createdBy:"user:dev",createdAt:"2026-08-14T00:00:00Z"}]});
    expect(result.items[0].blockers[0].code).toBe("PUBLICATION_REF_REQUIRED");
  });
  it("parses Responsibility assignment and fails closed on drift",()=>{
    const slot={slotId:"review",responsibilityType:"independent_review",requiredCapabilityIds:["review"],inputSchemaRef:{resourceType:"Schema",resourceId:"in",revision:null,authority:"aip"},outputSchemaRef:{resourceType:"Schema",resourceId:"out",revision:"1",authority:"aip"},gateRefs:[],returnStage:"review",assignee:{kind:"human_principal",resourceId:"user:reviewer",version:1}};
    const value={tenant,count:1,items:[{tenant,planId:"plan-1",revision:1,version:1,profile:"strict",templateRef:exact("ResponsibilityTemplateRevision","template-1"),slots:[slot],mergeDecisions:[],coverage:"complete",uncoveredSlots:[],contentHash:hash,lifecycle:"draft",readiness:"ready",blockers:[],createdBy:"user:dev",createdAt:"2026-08-14T00:00:00Z"}]};
    expect(parseResponsibilityPlanList(value).items[0].slots[0].assignee.kind).toBe("human_principal");
    expect(()=>parseResponsibilityPlanList({...value,count:2})).toThrow("不一致");
    expect(()=>parseEvalContractList({tenant,count:1,items:[{...value.items[0],contractId:"e",suiteRef:exact("EvalSuiteRevision","s"),publicationRef:null,releaseGateRef:null,artifactSchemaRef:slot.inputSchemaRef,severityThresholds:{bad:2},gatePolicy:{},returnMapping:{},overridePolicy:{}}]})).toThrow("0..1");
  });
});
