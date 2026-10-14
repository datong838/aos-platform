// Task-local connect wait only. No TLS/auth/retry/validator changes.
const u=require('/Users/ddt/work/projects/ai_agent/prime-agent/node_modules/undici');
const Original=u.EnvHttpProxyAgent;
u.EnvHttpProxyAgent=class extends Original { constructor(options={}) { super({...options,connectTimeout:60000}); } };
