// Synthetic transport only: no real user credentials, financial commands or approvals.
// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { createServer as createViteServer, preview as createPreviewServer } from 'vite';
// Runtime-only Node/config imports keep server modules out of the browser tsc graph.
// This project intentionally has no @types/node dependency; do not alter its lockfile.
const httpModule = 'node:http';
const configModule = '../../vite.config';
const { createServer: createHttpServer } = await import(httpModule);
const { createBudgetRenewalTransport } = await import(configModule);
type Server = ReturnType<typeof createHttpServer>;
type TestRequest = { url?: string; headers: Record<string, string | undefined>;
  on(event: string, callback: (chunk: string) => void): void };
type TestResponse = { end(body: string): void; setHeader(name: string, value: string): void };

const prefix = '/api/v1/aip/budget-policy-renewal';
async function listen(server: Server, port = 0): Promise<number> {
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => { server.off('error', reject); resolve(); });
  });
  return (server.address() as { port: number }).port;
}
async function close(server: Server) {
  if (!server.listening) return;
  server.closeAllConnections();
  await new Promise<void>((resolve, reject) => server.close((error?: Error) => error ? reject(error) : resolve()));
}

describe('private renewal transport target', () => {
  it.each([undefined, '', ' http://127.0.0.1:18462', 'http://127.0.0.1:18462 ',
    'http://localhost:18462', 'http://[::1]:18462', 'https://127.0.0.1:18462',
    'http://127.0.0.1:18463', 'http://127.0.0.1:18462/', 'http://127.0.0.1:18462?x=1',
    'http://127.0.0.1:18462#x', 'http://user:pass@127.0.0.1:18462',
    'http://127.0.0.1:18462@evil.invalid', 'http://2130706433:18462',
    'HTTP://127.0.0.1:18462', 'http://127.0.0.1:018462', '//127.0.0.1:18462',
    'http://evil.invalid:18462'])('does not create a private upstream for %s', target => {
    expect(createBudgetRenewalTransport(target).proxy).toEqual({});
  });
  it('accepts only the registered loopback listener and never enables websocket forwarding', () => {
    const transport = createBudgetRenewalTransport('http://127.0.0.1:18462');
    expect(Object.keys(transport.proxy)).toEqual([prefix]);
    expect(transport.proxy[prefix]).toMatchObject({ target: 'http://127.0.0.1:18462', changeOrigin: true, ws: false });
  });
});

describe('actual Vite request routing', () => {
  it('also closes the real preview proxy before inherited generic routing', async () => {
    const transport = createBudgetRenewalTransport('http://untrusted.invalid');
    const received: string[] = [];
    const upstream = createHttpServer((req: TestRequest, res: TestResponse) => { received.push(req.url!); res.end('original-api'); });
    const upstreamPort = await listen(upstream);
    let preview: Awaited<ReturnType<typeof createPreviewServer>> | undefined;
    try {
      preview = await createPreviewServer({ configFile: false, logLevel: 'silent', plugins: transport.plugins,
        server: { proxy: { ...transport.proxy, '/api': { target: `http://127.0.0.1:${upstreamPort}`, rewrite: path => path.replace(/^\/api/, '') } } },
        preview: { host: '127.0.0.1', port: 0 } });
      const base = `http://127.0.0.1:${(preview.httpServer.address() as {port: number}).port}`;
      const response = await fetch(base + prefix + '/propose', { method: 'POST', body: 'synthetic-only' });
      expect(response.status).toBe(503);
      expect(await response.json()).toEqual({ error: 'BUDGET_RENEWAL_GATEWAY_UNAVAILABLE' });
      expect(received).toEqual([]);
      expect(await (await fetch(base + '/api/v1/existing-read')).text()).toBe('original-api');
      expect(received).toEqual(['/v1/existing-read']);
    } finally { if (preview) await close(preview.httpServer); await close(upstream); }
  });
  it('returns closed503 without falling into generic API while other API requests work', async () => {
    const transport = createBudgetRenewalTransport(undefined);
    const received: string[] = [];
    const upstream = createHttpServer((req: TestRequest, res: TestResponse) => { received.push(req.url!); res.end('original-api'); });
    const upstreamPort = await listen(upstream);
    let vite: Awaited<ReturnType<typeof createViteServer>> | undefined;
    try {
      vite = await createViteServer({ configFile: false, logLevel: 'silent',
      plugins: transport.plugins, server: { host: '127.0.0.1', port: 0, hmr: false,
        proxy: { ...transport.proxy, '/api': { target: `http://127.0.0.1:${upstreamPort}`, rewrite: path => path.replace(/^\/api/, '') } } } });
      await vite.listen();
      const base = `http://127.0.0.1:${(vite.httpServer!.address() as {port: number}).port}`;
      for (const suffix of ['', '/propose', '/requests/propose/unit-only', '?read=1', '-reserved']) {
        const response = await fetch(base + prefix + suffix, { method: 'POST', body: '{"synthetic":true}' });
        expect(response.status).toBe(503);
        expect(response.headers.get('cache-control')).toBe('no-store');
        expect(await response.json()).toEqual({ error: 'BUDGET_RENEWAL_GATEWAY_UNAVAILABLE' });
      }
      expect(received).toEqual([]);
      expect(await (await fetch(base + '/api/v1/existing-read')).text()).toBe('original-api');
      expect(received).toEqual(['/v1/existing-read']);
    } finally { await vite?.close(); await close(upstream); }
  });

  it('forwards one private request with original Origin and bearer only to the owned fixed listener', async () => {
    const transport = createBudgetRenewalTransport('http://127.0.0.1:18462');
    const received: unknown[] = [];
    const gateway = createHttpServer((req: TestRequest, res: TestResponse) => {
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', () => { received.push({ path: req.url, host: req.headers.host,
        origin: req.headers.origin, authorization: req.headers.authorization, body });
        res.setHeader('content-type', 'application/json'); res.end('{"syntheticTransport":true}'); });
    });
    // EADDRINUSE is a failure before any request; never contact an unknown process.
    await listen(gateway, 18462);
    let vite: Awaited<ReturnType<typeof createViteServer>> | undefined;
    try {
      vite = await createViteServer({ configFile: false, logLevel: 'silent', plugins: transport.plugins,
      server: { host: '127.0.0.1', port: 0, hmr: false, proxy: transport.proxy } });
      await vite.listen();
      const base = `http://127.0.0.1:${(vite.httpServer!.address() as {port: number}).port}`;
      const response = await fetch(base + prefix + '/propose', { method: 'POST',
        headers: { Origin: base, Authorization: 'Bearer synthetic-not-a-jwt', 'content-type': 'application/json' },
        body: '{"synthetic":true}' });
      expect(response.status).toBe(200);
      expect(await response.json()).toEqual({ syntheticTransport: true });
      expect(received).toEqual([{ path: '/v1/aip/budget-policy-renewal/propose', host: '127.0.0.1:18462',
        origin: base, authorization: 'Bearer synthetic-not-a-jwt', body: '{"synthetic":true}' }]);
    } finally { await vite?.close(); await close(gateway); }
  });
});
