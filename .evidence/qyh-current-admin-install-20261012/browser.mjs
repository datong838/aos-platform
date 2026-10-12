import pw from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';
const root=new URL('.',import.meta.url).pathname;
const browser=await pw.chromium.connectOverCDP('http://127.0.0.1:9244');
const page=await browser.contexts()[0].newPage();const errors=[];page.on('pageerror',e=>errors.push(e.name));
try {
 const response=await page.goto('http://127.0.0.1:18434/apollo/assets');
 await page.getByText('栖月汇商贸有限公司',{exact:false}).first().waitFor({timeout:30000});
 await page.waitForTimeout(2000);
 const text=await page.locator('body').innerText();
 const result={url:page.url(),documentStatus:response.status(),tenantNameVisible:text.includes('栖月汇商贸有限公司'),installationManagementVisible:text.includes('安装管理'),newInstallationVisible:text.includes('栖月汇 · 电商资产包与八工作台恢复'),pageErrors:errors,eightPagesAccepted:false,tabRetained:true};
 await page.screenshot({path:root+'asset-management.png',fullPage:true});
 fs.writeFileSync(root+'browser-result.json',JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));
} finally {await browser.close();}
