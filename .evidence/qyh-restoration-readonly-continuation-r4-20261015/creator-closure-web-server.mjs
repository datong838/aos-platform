import { createServer } from '/Users/ddt/work/projects/ai_agent/aos-platform/apps/web/node_modules/vite/dist/node/index.js';
import fs from 'node:fs';
import path from 'node:path';
const task = path.dirname(new URL(import.meta.url).pathname);
const frozen = JSON.parse(fs.readFileSync(path.join(task, 'creator-closure-web-source.json')));
process.env.VITE_AOS_API_PROXY_TARGET = frozen.apiTarget;
delete process.env.VITE_AOS_API_BASE;
const server = await createServer({
  root: path.join(frozen.source, 'apps/web'),
  configFile: path.join(frozen.source, 'apps/web/vite.config.ts'),
  cacheDir: path.join(task, 'private/creator-closure-vite-cache'),
  server: { host: '127.0.0.1', port: frozen.port, strictPort: true },
});
await server.listen();
console.log(JSON.stringify({ outcome: 'LOCAL_HUMAN_LOGIN_WEB_LISTENING', port: frozen.port, apiPort: 18080, head: frozen.head, eightPagesAccepted: false }));
