// Hermetic UI acceptance only. Every API request is intercepted; no live AOS writes.
import { chromium } from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import { writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const out=new URL('.',import.meta.url).pathname;
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const id='12345678-1234-4234-8234-123456789012', actor='ui-fixture-operator';
const scope={orgId:'org-org',projectId:'dev-project',subject:actor,roles:['admin'],workspaceName:'隔离UI验收'};
const hash=v=>'sha256:'+createHash('sha256').update(JSON.stringify(v)).digest('hex');
const ref=(type,prefix,revision=1)=>({resourceType:type,resourceId:prefix+id,revision,contentHash:hash(type)});
const policy={...ref('SnapshotRelationshipPolicy',''),resourceId:'content/policies/relationships.json',revision:'1.0.0'};
const pipelines=['P01-shop-qyh','P02-product-qyh','P03-product-sku-qyh','P04-category-qyh','P05-order-qyh','P06-order-line-qyh','P07-shipment-qyh','P08-customer-lite-qyh','P09-weapp-qyh','P10-system-config-qyh','P11-product-review-qyh','P12-payment-qyh'];
const members=pipelines.map((pipelineId,i)=>({scheduleId:'fixture-schedule-'+i,pipelineId,bindingRef:ref('PipelineScheduleControlBinding','schedule-control-'),controlRef:ref('PipelineRuntimeControlRevision','pipeline-control-')}));
let mode='ready',current=null,writes=0,lost=false,phase='disabled';const receipts=new Map(),errors=[];
page.on('pageerror',error=>errors.push(error.message));
await page.addInitScript(scope=>{sessionStorage.setItem('aos-tenant-v1',JSON.stringify(scope));localStorage.setItem('aos-api-base-v1','/api');},scope);
await page.route('**/*',async route=>{
 const request=route.request(),url=new URL(request.url()),path=url.pathname;
 if(url.origin==='http://127.0.0.1:15174'&&!path.startsWith('/api'))return route.continue();
 const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 if(!path.startsWith('/api'))return route.abort('blockedbyclient');
 const p=path.slice(4);
 if(request.method()!=='GET'){writes++;return reply({message:'status acceptance is read-only'},409);}
 if(p==='/v1/me')return reply({...scope,markings:[],tokenKind:'fixture'});
 if(p.includes('health'))return reply({status:'ok'});
 if(p==='/v1/bundle-installations')return reply({items:[{installationId:id,displayName:'隔离验收实例（非真实商城）',state:'active',currentRevision:5,activeRevision:5,previousActiveRevision:null,etagVersion:5,createdAt:'2026-09-16T00:00:00Z',updatedAt:'2026-09-16T00:00:00Z'}],total:1,limit:50,offset:0});
 if(p==='/v1/bundle-runtime-installations/'+id)return reply({installationId:id,installationRevision:5,installationEtag:5,installationState:'active',effectiveState:'ready',binding:{generation:id,installationRevision:5,profileRef:'fixture-profile',configRef:null,executionEpoch:1,desiredState:'ready',observedState:'ready',enabled:true,operationFence:false,revision:1},currentOperation:null,ui:null,allowedActions:['configure','enable','disable'],reasons:[]});
 const base='/v1/pipelines/snapshot-schedules';
 if(p===base+'/'+id+'/runtime')return reply({orgId:scope.orgId,projectId:scope.projectId,definitionId:id,definitionRef:phase==='drift'?{...current.ref,revision:99}:current.ref,configurationState:'enabled',executionAuthorized:false,routingStatus:['pending','approved'].includes(phase)?'original_group_pending':'not_due',originalGroups:['pending','approved'].includes(phase)?[{groupId:id,recoveryRef:phase==='approved'?ref('SnapshotGroupRecoveryRevision','snapshot-recovery-'):null}]:[],observedAt:new Date().toISOString(),worker:{state:phase==='disabled'?'DISABLED':phase==='running'?'RUNNING':'IDLE',available:phase!=='disabled',active:phase==='running',errorCode:null}});
 if(p===base+'/definitions')return reply({items:current?[current]:[],nextCursor:null});
 if(p===base+'/options')return reply({installationId:id,generation:id,status:mode==='incomplete'?'incomplete':'ready',missing:mode==='incomplete'?pipelines.slice(2):[],ambiguous:[],members:mode==='incomplete'?[]:members.map(m=>({...m,definitionId:current?.body.state==='retired'?null:current?.body.definitionId||null})),policies:mode==='incomplete'?[]:[policy]});
 if(p.startsWith(base+'/')&&p.includes('/receipts/')){const key=decodeURIComponent(p.split('/receipts/')[1]);return receipts.has(key)?reply(receipts.get(key)):reply({message:'原回执未找到'},404);}
 if(p.startsWith(base+'/')&&request.method()==='GET')return current?reply(current):reply({message:'不存在'},404);
 if(request.method()!=='GET')return reply({message:'隔离验收禁止其他写操作'},409);
 return reply({items:[],total:0,limit:50,offset:0});
});

current={ref:ref('SnapshotScheduleDefinitionRevision','snapshot-schedule-',2),body:{schemaVersion:'aos.snapshot-schedule-definition/v1',orgId:scope.orgId,projectId:scope.projectId,definitionId:id,revision:2,priorRef:ref('SnapshotScheduleDefinitionRevision','snapshot-schedule-'),installationId:id,generation:id,state:'enabled',cron:'0 8 * * *',timezone:'Asia/Shanghai',policyRef:policy,members,actor,executor:'fixture-runtime',createdAt:new Date().toISOString()}};
const check=(ok,message)=>{if(!ok)throw new Error(message);};
try{
 await page.goto('http://127.0.0.1:15174/data/schedules');
 await page.getByRole('tab',{name:'整组采集',exact:true}).click();
 await page.locator('.snapshot-groups__item').click();
 await page.getByText('执行器尚未启用',{exact:true}).waitFor();
 await page.screenshot({path:out+'01-worker-disabled-1440.png',fullPage:true});
 for(const [state,label] of [['running','正在执行当前数据组'],['pending','原任务尚未完成，需核对恢复条件'],['approved','原任务恢复已批准，等待执行器承接']]){
  phase=state;await page.getByRole('button',{name:'刷新运行状态',exact:true}).click();await page.getByText(label,{exact:true}).waitFor();
 }
 await page.screenshot({path:out+'02-approved-1440.png',fullPage:true});
 phase='drift';await page.getByRole('button',{name:'刷新运行状态',exact:true}).click();
 await page.getByText('运行状态尚未确认：运行状态的租户或配置版本已变化，请刷新配置',{exact:true}).waitFor();
 await page.screenshot({path:out+'03-definition-drift-1440.png',fullPage:true});
 phase='pending';await page.getByRole('button',{name:'刷新运行状态',exact:true}).click();await page.getByText('原任务尚未完成，需核对恢复条件',{exact:true}).waitFor();
 await page.setViewportSize({width:760,height:1000});await page.getByLabel('数据组运行状态',{exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:out+'04-pending-760.png',fullPage:true});
 check(await page.locator('.snapshot-groups').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'status panel overflow');
 check(writes===0,'unexpected fixture write');check(errors.length===0,errors.join(';'));
 await writeFile(out+'result.json',JSON.stringify({kind:'hermetic-status-ui-only',liveAosRequests:0,sourceReads:0,writesToFixture:writes,checks:['worker disabled','active definition','pending original','approved recovery','exact definition drift','760 width'],errors},null,2));
 console.log('Status UI fixture acceptance passed; no live requests or writes.');
}catch(error){await page.screenshot({path:out+'failure.png',fullPage:true});throw error;}finally{await browser.close();}
