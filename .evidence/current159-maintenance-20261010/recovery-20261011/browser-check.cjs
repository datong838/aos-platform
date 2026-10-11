const {chromium}=require('/Users/ddt/work/projects/ai_agent/aos-platform/node_modules/.pnpm/playwright-core@1.63.0/node_modules/playwright-core');
const fs=require('fs');const path=require('path');
(async()=>{
 const browser=await chromium.connectOverCDP('http://127.0.0.1:9244',{noDefaults:true});
 const context=browser.contexts()[0];const page=await context.newPage();
 const routes=['cockpit','content-campaign','operations','creator-growth','media-studio','analyst','price-governance','customer'];const results=[];
 for(const name of routes){
  await page.goto('http://127.0.0.1:8434/workshop/'+name,{waitUntil:'networkidle',timeout:30000});
  await page.getByText('电商工作台',{exact:true}).first().waitFor({timeout:15000});
  const text=await page.locator('body').innerText();
  results.push({route:name,url:page.url(),heading:text.includes('电商工作台'),denial:text.includes('当前工作台入口不可用'),text});
  await page.screenshot({path:path.join(__dirname,'page-'+name+'.png'),fullPage:true});
 }
 const result={at:new Date().toISOString(),method:'isolated actual Chromium DOM and screenshots',results,browser_retained:true,business_first_chain:false};
 fs.writeFileSync(path.join(__dirname,'browser-dom.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({pages:results.length,denialPages:results.filter(x=>x.denial).length,retained:true}));process.exit(0);
})().catch(e=>{console.error(e.message);process.exit(1)});
