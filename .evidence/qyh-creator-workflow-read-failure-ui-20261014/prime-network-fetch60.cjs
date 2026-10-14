// Task-only fetch dispatcher: waits for TLS/connect, preserves all TLS/auth/request fields.
const u=require('/Users/ddt/work/projects/ai_agent/prime-agent/node_modules/undici');
const dispatcher=new u.EnvHttpProxyAgent({connectTimeout:60000,headersTimeout:0,bodyTimeout:0});
const original=globalThis.fetch.bind(globalThis);
globalThis.fetch=(input,options)=>original(input,{...options,dispatcher});
