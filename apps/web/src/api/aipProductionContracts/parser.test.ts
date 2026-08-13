import { describe, expect, it } from "vitest";
import { parseBriefList, parseBundleList } from "./parser";
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
