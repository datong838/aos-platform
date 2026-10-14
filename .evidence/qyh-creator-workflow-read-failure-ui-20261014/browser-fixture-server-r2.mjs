import { createServer } from '/Users/ddt/work/projects/ai_agent/aos-platform/apps/web/node_modules/vite/dist/node/index.js';
import path from 'node:path';import fs from 'node:fs';
const E=path.dirname(new URL(import.meta.url).pathname);
const meta=JSON.parse(fs.readFileSync(path.join(E,'browser-fixture-config-r2.json'),'utf8'));
process.env.VITE_AOS_API_PROXY_TARGET='http://127.0.0.1:1';delete process.env.VITE_AOS_API_BASE;
const deny={name:'isolated-deny-api',configureServer(s){s.middlewares.use((req,res,next)=>{if(req.url.startsWith('/api')){res.statusCode=403;res.end('ISOLATED_API_DENIED');}else next();});}};
const server=await createServer({plugins:[deny],root:path.join(E,'private/browser-fixture-r2'),envDir:path.join(E,'private/browser-fixture-r2'),configFile:path.join(meta.source,'apps/web/vite.config.ts'),cacheDir:path.join(E,'private/fixture-cache-r2'),server:{host:'127.0.0.1',port:18574,strictPort:true,fs:{allow:[E,meta.source,'/Users/ddt/work/projects/ai_agent/aos-platform/apps/web/node_modules']}}});
server.middlewares.use((req,res,next)=>{if(req.url.startsWith('/api')){res.statusCode=403;res.end('ISOLATED_API_DENIED');}else next();});
await server.listen();console.log(JSON.stringify({port:18574,baseHead:meta.baseHead,candidateHash:meta.sourceHash,fixtureOnly:true,originalApiConnected:false}));
