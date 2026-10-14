const u=require('/Users/ddt/work/projects/ai_agent/prime-agent/node_modules/undici');
const dispatcher=new u.EnvHttpProxyAgent({connectTimeout:60000,headersTimeout:0,bodyTimeout:0});
const original=globalThis.fetch.bind(globalThis);
process.stderr.write(JSON.stringify({trace:'preload-active'})+'\n');
globalThis.fetch=async(input,options)=>{const t=Date.now();const x=new URL(typeof input==='string'?input:input.url);process.stderr.write(JSON.stringify({trace:'fetch-start',host:x.host,path:x.pathname})+'\n');try{const r=await original(input,{...options,dispatcher});process.stderr.write(JSON.stringify({trace:'fetch-response',status:r.status,elapsed:Date.now()-t})+'\n');return r;}catch(err){process.stderr.write(JSON.stringify({trace:'fetch-error',name:err.name,causeCode:err.cause?.code,elapsed:Date.now()-t})+'\n');throw err;}};
