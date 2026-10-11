import { chromium } from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';
const root = new URL('.', import.meta.url).pathname;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9244');
const context = browser.contexts()[0];
const page = await context.newPage();
let apiRequests = 0;
await page.route('**/api/**', route => { apiRequests++; return route.abort(); });
await page.route('**/__qyh_diagnosis_qa__', route => route.fulfill({ contentType: 'text/html', body: `<!doctype html><html lang="zh"><head><title>QYH isolated diagnosis QA</title><style>body{font-family:system-ui;background:#f1f5f9;color:#172033;margin:48px}main{max-width:960px;background:white;padding:32px}li{padding:12px}button,a{margin-right:24px}header{margin-bottom:20px}</style></head><body><header>隔离界面验收 · 不代表正式安装激活</header><main id="root"></main><script type="module">
import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window);window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
const React=await import('/node_modules/.vite/deps/react.js');
const {createRoot}=await import('/node_modules/.vite/deps/react-dom_client.js');
const {MemoryRouter}=await import('/node_modules/.vite/deps/react-router-dom.js');
const {assetControlClient}=await import('/src/api/assetControl/client.ts');
const {WorkshopInstallationDiagnosis}=await import('/src/components/workshop/WorkshopInstallationDiagnosis.tsx');
const id='ccdcb0f0-1040-4bc6-aa0c-d045f5689813';
assetControlClient.listInstallations=async()=>({items:[{installationId:id,displayName:'栖月汇当前源码电商八工作台隔离首装',state:'approved',currentRevision:3,activeRevision:null,previousActiveRevision:null,etagVersion:3,createdAt:'2026-09-27T00:00:00Z',updatedAt:'2026-09-27T00:00:00Z'}],total:1,limit:5,offset:0});
assetControlClient.getRuntimeInstallation=async()=>({installationId:id,installationRevision:3,installationEtag:3,installationState:'approved',effectiveState:'not_prepared',binding:null,currentOperation:null,ui:null,allowedActions:['runtime-apply'],reasons:[],preparationExecutable:false});
createRoot(document.getElementById('root')).render(React.createElement(MemoryRouter,null,React.createElement(WorkshopInstallationDiagnosis)));
</script></body></html>` }));
try {
 await page.goto('http://127.0.0.1:8434/__qyh_diagnosis_qa__');
 await page.getByText('运行资源尚未准备。', {exact:false}).waitFor({timeout:15000});
 const text=await page.locator('main').innerText();
 if(!text.includes('已批准') || !text.includes('栖月汇') || apiRequests!==0) throw new Error('QA assertion failed');
 await page.screenshot({path:root+'browser-qa.png',fullPage:true});
 fs.writeFileSync(root+'browser-qa.json',JSON.stringify({scope:'ISOLATED_COMPONENT_UI_ONLY',url:page.url(),apiRequests,formalActivationProven:false,text},null,2));
 console.log(JSON.stringify({result:'ISOLATED_UI_PASS',apiRequests,formalActivationProven:false}));
} finally { await browser.close(); }
