import { describe, expect, it } from 'vitest';
import { executableConfig, verifySaved, verifyDiscovery } from './sourceSetup';
describe('saved source contracts',()=>{
 it('sends only connector fields and numeric ports',()=>{
  const result=executableConfig('jdbc-mysql-ssh',{sshHost:'host',sshPort:'22',dbPort:'3306',password:'test',apiKey:'ignored',sshKeyRef:''});
  expect(result).toEqual({sshHost:'host',sshPort:22,dbPort:3306,password:'test'});
 });
 it('does not invent a successful identity',()=>{expect(()=>verifySaved({id:'wrong',configurationRevision:''},'expected')).toThrow();});
 it('rejects discovery for a different saved version',()=>{
  expect(()=>verifyDiscovery({ok:true,sourceId:'source',configurationRevision:'old',tables:[],truncated:false,latencyMs:1},{id:'source',configurationRevision:'new'})).toThrow();
 });
});
