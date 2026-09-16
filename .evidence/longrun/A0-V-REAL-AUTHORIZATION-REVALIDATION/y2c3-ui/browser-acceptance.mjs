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
let mode='incomplete',current=null,writes=0,lost=false;const receipts=new Map(),errors=[];
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
 const base='/v1/pipelines/snapshot-schedules';
 if(p===base+'/definitions')return reply({items:current?[current]:[],nextCursor:null});
 if(p===base+'/options')return reply({installationId:id,generation:id,status:mode==='incomplete'?'incomplete':'ready',missing:mode==='incomplete'?pipelines.slice(2):[],ambiguous:[],members:mode==='incomplete'?[]:members.map(m=>({...m,definitionId:current?.body.state==='retired'?null:current?.body.definitionId||null})),policies:mode==='incomplete'?[]:[policy]});
 if(p.startsWith(base+'/')&&p.includes('/receipts/')){const key=decodeURIComponent(p.split('/receipts/')[1]);return receipts.has(key)?reply(receipts.get(key)):reply({message:'原回执未找到'},404);}
 if(p.startsWith(base+'/')&&['PUT','POST'].includes(request.method())){
  writes++;const pieces=p.slice(base.length+1).split('/'),definitionId=pieces[0],intent=request.method()==='PUT'?'configure':pieces[1],input=request.postDataJSON(),key=request.headers()['idempotency-key'];
  const settings=intent==='configure'?{cron:input.cron,policyRef:input.policyRef,members}:null;
  const body={schemaVersion:'aos.snapshot-schedule-definition/v1',orgId:scope.orgId,projectId:scope.projectId,definitionId,revision:current?current.body.revision+1:1,priorRef:input.expectedRef,installationId:id,generation:id,state:({configure:'disabled',enable:'enabled',disable:'disabled',retire:'retired'})[intent],cron:settings?.cron||current.body.cron,timezone:'Asia/Shanghai',policyRef:policy,members,actor,executor:'fixture-runtime',createdAt:new Date().toISOString()};
  current={ref:{resourceType:'SnapshotScheduleDefinitionRevision',resourceId:'snapshot-schedule-'+definitionId,revision:body.revision,contentHash:hash(body)},body};
  const requestBody={orgId:scope.orgId,projectId:scope.projectId,definitionId,actor,intent,expectedRef:input.expectedRef,settings};
  receipts.set(key,{...current,idempotencyKey:key,requestHash:hash(requestBody),request:requestBody});
  if(!lost){lost=true;return route.abort('failed');}return reply(current);
 }
 if(p.startsWith(base+'/')&&request.method()==='GET')return current?reply(current):reply({message:'不存在'},404);
 if(request.method()!=='GET')return reply({message:'隔离验收禁止其他写操作'},409);
 return reply({items:[],total:0,limit:50,offset:0});
});
const check=(condition,message)=>{if(!condition)throw new Error(message);};
try{
 await page.goto('http://127.0.0.1:15174/data/schedules');
 await page.getByRole('tab',{name:'整组采集',exact:true}).click();
 await page.getByLabel('已安装实例',{exact:true}).selectOption(id);
 await page.getByText('来源尚未就绪',{exact:true}).waitFor();
 check(await page.getByRole('button',{name:'保存为停用配置'}).isDisabled(),'incomplete group unexpectedly enabled save');
 await page.screenshot({path:out+'01-incomplete-1440.png',fullPage:true});
 mode='ready';await page.getByLabel('已安装实例',{exact:true}).selectOption('');await page.getByLabel('已安装实例',{exact:true}).selectOption(id);
 await page.getByRole('button',{name:'保存为停用配置'}).click();
 await page.getByText('有一项待确认操作',{exact:true}).waitFor();check(writes===1,'duplicate initial write');
 await page.reload();await page.getByRole('tab',{name:'整组采集',exact:true}).click();await page.getByText('有一项待确认操作',{exact:true}).waitFor();check(writes===1,'reload resent pending write');
 await page.screenshot({path:out+'02-pending-reload-1440.png',fullPage:true});
 await page.getByRole('button',{name:'核对原操作',exact:true}).click();await page.getByText('已找到并核对原操作回执。',{exact:true}).waitFor();check(writes===1,'receipt check wrote again');
 await page.locator('.snapshot-groups__item').click();
 await page.getByRole('button',{name:'启用配置',exact:true}).click();await page.getByRole('button',{name:'停用配置',exact:true}).waitFor();
 await page.getByRole('button',{name:'停用配置',exact:true}).click();await page.getByRole('button',{name:'退役配置',exact:true}).waitFor();
 await page.getByRole('button',{name:'退役配置',exact:true}).click();await page.getByRole('button',{name:'确认退役',exact:true}).click();
 await page.getByText('原操作回执已核对。已退役',{exact:true}).waitFor();check(writes===4,'unexpected write count');
 await page.screenshot({path:out+'03-retired-1440.png',fullPage:true});
 await page.setViewportSize({width:760,height:1000});await page.screenshot({path:out+'04-retired-760.png',fullPage:true});
 await page.locator('.snapshot-groups__editor').scrollIntoViewIfNeeded();await page.screenshot({path:out+'05-editor-760.png',fullPage:true});
 check(await page.locator('.snapshot-groups').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'new group panel has horizontal overflow');
 check(errors.length===0,'browser runtime errors: '+errors.join(';'));
 await writeFile(out+'result.json',JSON.stringify({kind:'hermetic-ui-only',liveAosRequests:0,sourceReads:0,writesToFixture:writes,checks:['incomplete disabled','commit acknowledgement lost','reload zero resend','original receipt GET','enable','disable','retire','responsive'],errors},null,2));
 console.log('UI fixture acceptance passed; no live AOS requests; 4 fixture commands, no duplicate.');
}catch(error){await page.screenshot({path:out+'failure.png',fullPage:true});await writeFile(out+'failure.txt',page.url()+'\n'+await page.locator('body').innerText());throw error;}finally{await browser.close();}
