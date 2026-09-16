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
let mode='ready',current=null,writes=0,lost=false,phase='pending';const receipts=new Map(),errors=[];
page.on('pageerror',error=>errors.push(error.message));
await page.addInitScript(scope=>{sessionStorage.setItem('aos-tenant-v1',JSON.stringify(scope));localStorage.setItem('aos-api-base-v1','/api');},scope);
await page.route('**/*',async route=>{
 const request=route.request(),url=new URL(request.url()),path=url.pathname;
 if(url.origin==='http://127.0.0.1:15174'&&!path.startsWith('/api'))return route.continue();
 const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 if(!path.startsWith('/api'))return route.abort('blockedbyclient');
 const p=path.slice(4);

 if(p==='/v1/me')return reply({...scope,markings:[],tokenKind:'fixture'});
 if(p.includes('health'))return reply({status:'ok'});
 if(p==='/v1/bundle-installations')return reply({items:[{installationId:id,displayName:'隔离验收实例（非真实商城）',state:'active',currentRevision:5,activeRevision:5,previousActiveRevision:null,etagVersion:5,createdAt:'2026-09-16T00:00:00Z',updatedAt:'2026-09-16T00:00:00Z'}],total:1,limit:50,offset:0});
 if(p==='/v1/bundle-runtime-installations/'+id)return reply({installationId:id,installationRevision:5,installationEtag:5,installationState:'active',effectiveState:'ready',binding:{generation:id,installationRevision:5,profileRef:'fixture-profile',configRef:null,executionEpoch:1,desiredState:'ready',observedState:'ready',enabled:true,operationFence:false,revision:1},currentOperation:null,ui:null,allowedActions:['configure','enable','disable'],reasons:[]});
 const recovery='/v1/pipelines/snapshot-recoveries/'+id;
 if(p===recovery&&request.method()==='GET'){
  const now=Date.now();return reply({status:'saved_input_verified',executionAuthorized:false,groupId:id,originalDefinitionRef:{...current.ref,revision:1},expectedDefinitionRef:current.ref,expectedRecoveryRef:null,inputManifestHash:hash('original-input'),observation:{startedAt:new Date(now-7200000).toISOString(),completedAt:new Date(now-7199000).toISOString()},windowRules:{maxDurationHours:24,notBeforeMinimum:new Date(now-10800000).toISOString(),expiresAfter:new Date(now-3600000).toISOString(),currentTime:new Date(now).toISOString()},runStates:[{status:'failed',executorStopped:true,finishedAt:new Date(now-1800000).toISOString(),count:12}]});
 }
 if(p===recovery+'/renew'&&request.method()==='POST'){
  writes++;const input=request.postDataJSON(),key=request.headers()['idempotency-key'],old=current;
  current={body:{...old.body,revision:old.body.revision+1,priorRef:old.ref,createdAt:new Date().toISOString()}};
  current.ref={...old.ref,revision:current.body.revision,contentHash:hash(current.body)};
  const requestBody={schemaVersion:'aos.snapshot-group-recovery-request/v1',orgId:scope.orgId,projectId:scope.projectId,groupId:id,actor,...input};
  const body={schemaVersion:'aos.snapshot-group-recovery/v1',mode:'saved-input-only',orgId:scope.orgId,projectId:scope.projectId,groupId:id,revision:1,priorRef:null,originalDefinitionRef:{...old.ref,revision:1},currentDefinitionRef:current.ref,originalScheduleClaimHash:hash('original-schedule'),originalSourceClaimHash:hash('original-source'),inputManifestHash:input.inputManifestHash,actor,executor:'fixture-runtime',policyRef:policy,requestHash:hash(requestBody),createdAt:new Date().toISOString()};
  receipts.set(key,{ref:ref('SnapshotGroupRecoveryRevision','snapshot-recovery-'),body,request:requestBody,requestHash:body.requestHash,idempotencyKey:key});phase='approved';
  return route.abort('failed');
 }
 if(p.startsWith(recovery+'/receipts/')&&request.method()==='GET'){
  const key=decodeURIComponent(p.split('/receipts/')[1]);return receipts.has(key)?reply(receipts.get(key)):reply({message:'original missing'},404);
 }
 if(request.method()!=='GET')return reply({message:'other fixture writes forbidden'},409);
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
 await page.goto('http://127.0.0.1:15174/data/schedules');await page.getByRole('tab',{name:'整组采集',exact:true}).click();await page.locator('.snapshot-groups__item').click();
 await page.getByRole('button',{name:'核对原任务',exact:true}).click();
 await page.getByText(/原采集时间：/).waitFor();
 await page.getByLabel('原任务恢复',{exact:true}).screenshot({path:out+'01-original-context-form.png'});
 await page.getByRole('button',{name:'提交恢复申请',exact:true}).click();
 await page.getByText('有一项待确认恢复申请',{exact:true}).waitFor();check(writes===1,'duplicate initial renewal');
 await page.screenshot({path:out+'02-unknown-1440.png',fullPage:true});
 await page.reload();await page.getByRole('tab',{name:'整组采集',exact:true}).click();await page.getByText('有一项待确认恢复申请',{exact:true}).waitFor();check(writes===1,'reload resent renewal');
 await page.getByRole('button',{name:'核对原恢复申请',exact:true}).click();
 await page.getByText('原恢复申请回执已核对，等待执行器按当前条件承接。',{exact:true}).waitFor();
 await page.getByText('原任务恢复已批准，等待执行器承接',{exact:true}).waitFor();
 check(writes===1,'receipt confirmation wrote');check(await page.getByText('有一项待确认恢复申请',{exact:true}).count()===0,'pending was not cleared');
 await page.screenshot({path:out+'03-original-confirmed-1440.png',fullPage:true});
 await page.setViewportSize({width:760,height:1000});await page.getByLabel('数据组运行状态',{exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:out+'04-original-confirmed-760.png',fullPage:true});
 check(await page.locator('.snapshot-groups').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'new recovery panel overflow');check(errors.length===0,errors.join(';'));
 await writeFile(out+'result.json',JSON.stringify({kind:'hermetic-recovery-ui-only',liveAosRequests:0,sourceReads:0,writesToFixture:writes,checks:['original context GET','explicit window renewal','commit ack lost','reload zero resend','original receipt GET','current definition refresh','760 width'],errors},null,2));
 console.log('Original recovery UI passed: one fixture renewal, zero replay writes, zero live AOS requests.');
}catch(error){await page.screenshot({path:out+'failure.png',fullPage:true});await writeFile(out+'failure.txt',await page.locator('body').innerText());throw error;}finally{await browser.close();}
