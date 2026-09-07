import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { chromium } from "playwright-core";
import { build } from "../../../node_modules/.pnpm/esbuild@0.21.5/node_modules/esbuild/lib/main.js";

const evidenceDir = path.dirname(new URL(import.meta.url).pathname);
const repositoryRoot = path.resolve(evidenceDir, "../../..");
const temporaryRoot = fs.mkdtempSync(path.join(os.tmpdir(), "aos-ar1d-host-"));
const installationId = "11111111-1111-4111-8111-111111111111";
const generation = "22222222-2222-4222-8222-222222222222";
const extensionBody = `<!doctype html><html lang="zh-CN"><body>
<h1>隔离扩展机制验收</h1><p id="extension-status">等待宿主握手</p>
<script>
const identity={installationId:"${installationId}",generation:"${generation}",executionEpoch:3};
const nonce=new URLSearchParams(location.hash.slice(1)).get("aosNonce");
const status=document.getElementById("extension-status");
window.addEventListener("message",event=>{
  if(event.data?.type!=="aos:connected"||event.data.nonce!==nonce||!event.ports[0])return;
  const port=event.ports[0]; let step=0;
  port.onmessage=message=>{
    if(message.data?.type!=="response")return;
    step+=1;
    if(step===1){status.textContent="声明内读取成功";port.postMessage({version:1,type:"command",sequence:2,requestId:"command-1",...identity,operationId:"command.content.create",input:{title:"隔离验收"}});}
    else if(step===2){status.textContent="声明内命令成功，正在验证越界拒绝";port.postMessage({version:1,type:"read",sequence:3,requestId:"read-2",...identity,operationId:"read.secret",input:{}});}
  };
  port.start();
  port.postMessage({version:1,type:"read",sequence:1,requestId:"read-1",...identity,operationId:"read.orders",input:{limit:1}});
});
window.parent.postMessage({version:1,type:"aos:hello",nonce,...identity},"*");
</script></body></html>`;
const resourceHash = `sha256:${crypto.createHash("sha256").update(extensionBody).digest("hex")}`;

const entryPath = path.join(temporaryRoot, "entry.tsx");
const bundlePath = path.join(temporaryRoot, "host.js");
fs.writeFileSync(entryPath, `
import React, {useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {ExtensionHost} from ${JSON.stringify(path.join(repositoryRoot, "apps/web/src/components/extensions/ExtensionHost.tsx"))};
import {parseRuntimeInstallation} from ${JSON.stringify(path.join(repositoryRoot, "apps/web/src/api/assetControl/runtimeInstallations.ts"))};
function Harness(){const [runtime,setRuntime]=useState(null);const [log,setLog]=useState([]);const append=(v)=>setLog(x=>[...x,v]);useEffect(()=>{fetch("/api/runtime").then(r=>r.json()).then(v=>setRuntime(parseRuntimeInstallation(v))).catch(()=>append("api:error"))},[]);if(!runtime)return <main><h1>Canonical API 运行视图验收</h1><p>正在读取 API</p></main>;const hostSpec=runtime.ui?{installationId:runtime.installationId,generation:runtime.binding.generation,executionEpoch:runtime.binding.executionEpoch,...runtime.ui}:null;return <main><h1>Canonical API 运行视图验收</h1><pre id="host-log">{log.join("\\n")}</pre><ExtensionHost spec={hostSpec} effectiveState={runtime.effectiveState} onRead={(id)=>{append("read:"+id);return {rows:1}}} onCommand={(id)=>{append("command:"+id);return {receiptId:"receipt-1"}}}/></main>}
createRoot(document.getElementById("root")).render(<Harness/>);
`);
await build({
  entryPoints: [entryPath],
  outfile: bundlePath,
  bundle: true,
  format: "iife",
  platform: "browser",
  jsx: "automatic",
  logLevel: "silent",
  absWorkingDir: path.join(repositoryRoot, "apps/web"),
  nodePaths: [path.join(repositoryRoot, "apps/web/node_modules"), path.join(repositoryRoot, "node_modules")],
});
const hostHtml = "<!doctype html><html lang=zh-CN><body><div id=root></div><script src=/host.js></script></body></html>";

const apiProcess = spawn(path.join(repositoryRoot, "services/aos-api/.venv/bin/python"), [path.join(evidenceDir, "isolated_api.py")], {
  cwd: repositoryRoot,
  env: { ...process.env, PYTHONPATH: path.join(repositoryRoot, "services/aos-api"), AR1D_RESOURCE_HASH: resourceHash },
  stdio: ["ignore", "ignore", "pipe"],
});
let apiError = "";
apiProcess.stderr.on("data", chunk => { apiError += chunk.toString(); });
for (let attempt = 0; attempt < 300; attempt += 1) {
  try { const response = await fetch(`http://127.0.0.1:18184/v1/bundle-runtime-installations/${installationId}`); if (response.ok) break; } catch {}
  await new Promise(resolve => setTimeout(resolve, 100));
  if (attempt === 299) throw new Error(`isolated API did not start: ${apiError}`);
}

function server(port, responder) {
  const instance = http.createServer(responder);
  return new Promise((resolve, reject) => { instance.once("error", reject); instance.listen(port, "127.0.0.1", () => resolve(instance)); });
}
const resourceServer = await server(18182, (_request, response) => {
  response.writeHead(200, { "content-type": "text/html; charset=utf-8", "content-security-policy": "default-src 'none'; script-src 'unsafe-inline'" });
  response.end(extensionBody);
});
const hostServer = await server(18183, (request, response) => {
  if (request.url === "/host.js") { response.writeHead(200, { "content-type": "text/javascript" }); response.end(fs.readFileSync(bundlePath)); return; }
  if (request.url === "/api/runtime") {
    http.get(`http://127.0.0.1:18184/v1/bundle-runtime-installations/${installationId}`, upstream => { response.writeHead(upstream.statusCode ?? 502, upstream.headers); upstream.pipe(response); }).on("error", () => { response.writeHead(502); response.end(); });
    return;
  }
  response.writeHead(200, { "content-type": "text/html; charset=utf-8" }); response.end(hostHtml);
});

const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
let result;
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const failures = [];
  page.on("pageerror", error => failures.push(error.message));
  await page.goto("http://127.0.0.1:18183", { waitUntil: "networkidle" });
  await page.locator("#host-log").getByText("read:read.orders", { exact: false }).waitFor();
  await page.locator("#host-log").getByText("command:command.content.create", { exact: false }).waitFor();
  await page.getByRole("alert").getByText("扩展操作超出授权范围", { exact: true }).waitFor();
  const frame = page.frameLocator("iframe");
  await frame.getByText("声明内命令成功，正在验证越界拒绝", { exact: true }).waitFor();
  await page.screenshot({ path: path.join(evidenceDir, "isolated-host-browser.png"), fullPage: true });
  result = { schemaVersion: "aos.extension-host-browser/ar1-d-v1", result: failures.length ? "FAIL" : "PASS", resourceHash, observed: ["canonical-runtime-http-api", "server-ui-strict-parser", "sandbox-iframe", "nonce-message-channel", "claimed-read", "claimed-command", "unclaimed-read-fenced"], failures };
} finally {
  await browser.close();
  await new Promise(resolve => resourceServer.close(resolve));
  await new Promise(resolve => hostServer.close(resolve));
  apiProcess.kill("SIGTERM");
  fs.rmSync(temporaryRoot, { recursive: true, force: true });
}
fs.writeFileSync(path.join(evidenceDir, "isolated-host-browser.json"), `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify(result, null, 2));
if (result.result !== "PASS") process.exitCode = 1;
