import { describe, expect, it } from "vitest";
import { parseArtifactRelationList, parseBriefList, parseBundleList, parseEvalContractList, parseResponsibilityPlanList, parseReviewIssueList, parseStageTemplateList } from "./parser";
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

describe("W2-C production contract parser",()=>{
  const exact=(resourceType:string,resourceId:string)=>({resourceType,resourceId,revision:1,contentHash:hash});
  const schema=(resourceId:string)=>({resourceType:"Schema",resourceId,revision:"1",authority:"aip"});
  it("解析 Stage、Artifact relation 与 Review issue 权威列表",()=>{
    const stage={stageId:"analysis",title:"分析",dependsOn:[],applicability:{kind:"always",profiles:[]},requiredSlotIds:["analyst"],inputSchemaRef:schema("analysis.in"),outputSchemaRef:schema("analysis.out"),gateRefs:[],checkpointPolicy:{},retryPolicy:{},compensationPolicy:{}};
    const templates=parseStageTemplateList({tenant,count:1,items:[{tenant,templateId:"stage-1",revision:1,version:1,profile:"standard",sourceBundleRef:exact("AssetBundleRevision","bundle-1"),stages:[stage],contentHash:hash,lifecycle:"draft",sealedBy:null,sealedAt:null,sealHash:null,readiness:"blocked",blockers:[{code:"STAGE_SOURCE_AUTHORITY_UNAVAILABLE",message:"缺少权威解析器",resourceRef:exact("AssetBundleRevision","bundle-1")}],createdBy:"user:dev",createdAt:"2026-08-14T00:00:00Z"}]});
    expect(templates.items[0].stages[0].stageId).toBe("analysis");
    expect(parseArtifactRelationList({tenant,count:1,items:[{tenant,relationId:"relation-1",relationType:"derived_from",fromArtifact:{artifactId:"artifact-2",contentHash:hash},toArtifact:{artifactId:"artifact-1",contentHash:hash},reason:"生成",createdBy:"agent",createdAt:"2026-08-14T00:00:00Z"}]}).count).toBe(1);
    expect(parseReviewIssueList({tenant,count:1,items:[{tenant,issueId:"issue-1",ruleRef:exact("EvalRuleRevision","rule-1"),severity:"error",artifactRef:{artifactId:"artifact-2",contentHash:hash},evalReportRef:exact("EvalReportRevision","report-1"),location:{field:"title"},evidenceRefs:[exact("Evidence","evidence-1")],suggestedFix:"修正文案",returnStage:"draft",status:"open",version:1,createdBy:"reviewer",createdAt:"2026-08-14T00:00:00Z",updatedBy:"reviewer",updatedAt:"2026-08-14T00:00:00Z"}]}).items[0].status).toBe("open");
  });
  it("拒绝不完整 seal 与非法 relation",()=>{
    const value={tenant,count:1,items:[{tenant,templateId:"stage-1",revision:2,version:2,profile:"standard",sourceBundleRef:exact("AssetBundleRevision","bundle-1"),stages:[{stageId:"analysis",title:"分析",dependsOn:[],applicability:{kind:"always",profiles:[]},requiredSlotIds:["analyst"],inputSchemaRef:schema("in"),outputSchemaRef:schema("out"),gateRefs:[],checkpointPolicy:{},retryPolicy:{},compensationPolicy:{}}],contentHash:hash,lifecycle:"frozen",sealedBy:"user:dev",sealedAt:null,sealHash:hash,readiness:"ready",blockers:[],createdBy:"user:dev",createdAt:"2026-08-14T00:00:00Z"}]};
    expect(()=>parseStageTemplateList(value)).toThrow("seal");
    expect(()=>parseArtifactRelationList({tenant,count:1,items:[{tenant,relationId:"r",relationType:"bad",fromArtifact:{artifactId:"a",contentHash:hash},toArtifact:{artifactId:"b",contentHash:hash},reason:"x",createdBy:"u",createdAt:"now"}]})).toThrow("relationType");
  });
});
