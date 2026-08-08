#!/usr/bin/env python3
"""smoke2: 验证 navigate 是否真能启动 Chrome 并加载页面 + 截图 + 提取文字。
每个 MCP 调用都独立 timeout，卡死就抛。
"""
import os, sys, time, json, threading, traceback, http.client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = "/tmp/bp_smoke2"
os.makedirs(OUT, exist_ok=True)
LOG = open(f"{OUT}/log.txt", "w", buffering=1)

def log(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line, flush=True)
    print(line, file=LOG)

# 直接用 KitewrightMCP，不用 BrowserPilot 包装，更精确控制超时
from engine_adapter import KitewrightMCP, DEFAULT_KITE_ENDPOINT, DEFAULT_KITE_PORT

mcp = KitewrightMCP()
log("启动 kite MCP...")
t0 = time.time()
try:
    def start():
        mcp.start()
    t = threading.Thread(target=start, daemon=True)
    t.start(); t.join(timeout=30)
    if t.is_alive():
        raise RuntimeError("start() 超时 30s")
except Exception as e:
    log(f"启动失败: {e}\n{traceback.format_exc()}")
    try: mcp.stop()
    except: pass
    sys.exit(1)
log(f"启动完成，耗时 {time.time()-t0:.1f}s，session={mcp._session_id}")


def call(tool, params, timeout_s=60, desc=""):
    """带超时的 call_tool；超时返回 {'error':'timeout'}"""
    res = [None]
    err = [None]
    def _do():
        try:
            res[0] = mcp.call_tool(tool, params)
        except Exception as e:
            err[0] = e
    t = threading.Thread(target=_do, daemon=True)
    t.start(); t.join(timeout=timeout_s)
    if t.is_alive():
        log(f"  ⚠️ {desc or tool} 超时 {timeout_s}s")
        return {"error": f"timeout_{timeout_s}s"}
    if err[0] is not None:
        log(f"  ❌ {desc or tool} err: {err[0]}")
        return {"error": str(err[0])}
    return res[0]

# 1. navigate
log("(1) browser_navigate /data/pipelines ...")
r = call("browser_navigate", {"url": "http://127.0.0.1:5173/data/pipelines", "lite": False}, timeout_s=90, desc="navigate")
log(f"  result keys: {list(r.keys()) if isinstance(r, dict) else type(r).__name__}")
if isinstance(r, dict) and "error" in r:
    log(f"  error: {r['error'][:200]}")
time.sleep(3)

# 2. 等栖月汇出现
log("(2) wait_for 栖月汇 (15s)...")
r = call("browser_wait_for", {"text": "栖月汇", "timeout_ms": 15000}, timeout_s=25, desc="wait_for 栖月汇")
log(f"  result: {str(r)[:300]}")

# 3. extract body
log("(3) extract body ...")
r = call("browser_extract", {"selector": "body"}, timeout_s=20, desc="extract body")
body = ""
if isinstance(r, dict) and "result" in r:
    c = r["result"].get("content", [])
    if isinstance(c, list) and c and isinstance(c[0], dict):
        body = c[0].get("text", "")
log(f"  body len={len(body)}")
# 关键词
for kw in ["栖月汇-商品","栖月汇-商品SKU","管道","打开画布"]:
    log(f"  含 {kw!r}: {kw in body}")
with open(f"{OUT}/body.txt","w",encoding="utf-8") as f: f.write(body)

# 4. snapshot
log("(4) snapshot ...")
r = call("browser_snapshot", {"diff": False}, timeout_s=20, desc="snapshot")
snap = ""
if isinstance(r, dict) and "result" in r:
    c = r["result"].get("content", [])
    if isinstance(c, list) and c and isinstance(c[0], dict):
        snap = c[0].get("text", "")
log(f"  snapshot len={len(snap)}")
with open(f"{OUT}/snapshot.txt","w",encoding="utf-8") as f: f.write(snap)

# 5. screenshot
log("(5) screenshot ...")
r = call("browser_screenshot", {"full_page": True}, timeout_s=30, desc="screenshot")
import base64
png = b""
if isinstance(r, dict) and "result" in r:
    c = r["result"].get("content", [])
    if isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get("type") == "image":
        b64 = c[0].get("data", "")
        try: png = base64.b64decode(b64)
        except Exception as e: log(f"  decode png err: {e}")
log(f"  png size={len(png)} bytes")
if png:
    with open(f"{OUT}/pipelines.png","wb") as f: f.write(png)

# 6. click「栖月汇-商品」卡的「打开画布」
log("(6) 点击 栖月汇-商品 的 打开画布...")
# 先试：点击文字「栖月汇-商品」
r = call("browser_click", {"selector": "text=栖月汇-商品", "timeout_ms": 8000}, timeout_s=20, desc="click 栖月汇-商品")
log(f"  click result: {str(r)[:200]}")
time.sleep(3)

# 7. 等 Builder 字样
log("(7) wait_for Builder/画布 ...")
r = call("browser_wait_for", {"text": "Builder", "timeout_ms": 20000}, timeout_s=30, desc="wait_for Builder")
log(f"  result: {str(r)[:200]}")
# 没等到的话 fallback 到 「画布」
if isinstance(r, dict) and "error" in r:
    r = call("browser_wait_for", {"text": "画布", "timeout_ms": 10000}, timeout_s=20, desc="wait_for 画布")
    log(f"  fallback result: {str(r)[:200]}")
time.sleep(2)

# 8. 画布截图 + 文字提取
log("(8) canvas extract + screenshot...")
r = call("browser_extract", {"selector": "body"}, timeout_s=20, desc="canvas extract")
body2 = ""
if isinstance(r, dict) and "result" in r:
    c = r["result"].get("content", [])
    if isinstance(c, list) and c and isinstance(c[0], dict):
        body2 = c[0].get("text", "")
log(f"  body2 len={len(body2)}")
for kw in ["goods_state","source_filter","site_filter","niushop","source","Source","输入"]:
    log(f"  含 {kw!r}: {kw in body2}")
with open(f"{OUT}/canvas_body.txt","w",encoding="utf-8") as f: f.write(body2)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30, desc="screenshot canvas")
png2 = b""
if isinstance(r, dict) and "result" in r:
    c = r["result"].get("content", [])
    if isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get("type") == "image":
        try: png2 = base64.b64decode(c[0].get("data", ""))
        except: pass
if png2:
    with open(f"{OUT}/canvas.png","wb") as f: f.write(png2)

# 9. 点 Source/输入/niushop 节点
log("(9) 点 Source / 输入 / niushop 节点...")
for sel in ["text=niushop-qyh", "text=输入", "text=Source", "text=niushop"]:
    log(f"  尝试: {sel}")
    r = call("browser_click", {"selector": sel, "timeout_ms": 5000}, timeout_s=15, desc=f"click {sel}")
    if isinstance(r, dict) and "error" not in r:
        log(f"  ✅ 点中了: {sel}")
        break
    else:
        if isinstance(r, dict):
            log(f"  fail: {str(r.get('error',''))[:100]}")
time.sleep(2)

# 10. 属性面板文本 + 截图
log("(10) 属性面板 extract...")
r = call("browser_extract", {"selector": "body"}, timeout_s=20, desc="prop panel extract")
body3 = ""
if isinstance(r, dict) and "result" in r:
    c = r["result"].get("content", [])
    if isinstance(c, list) and c and isinstance(c[0], dict):
        body3 = c[0].get("text", "")
log(f"  body3 len={len(body3)}")
for kw in ["goods_state","source_filter","site_filter","sourceFilter","过滤","输入源","表","过滤条件"]:
    log(f"  含 {kw!r}: {kw in body3}")
has = "goods_state=1" in body3
log(f"  goods_state=1 FOUND: {has}")
with open(f"{OUT}/prop_body.txt","w",encoding="utf-8") as f: f.write(body3)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30, desc="screenshot prop")
png3 = b""
if isinstance(r, dict) and "result" in r:
    c = r["result"].get("content", [])
    if isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get("type") == "image":
        try: png3 = base64.b64decode(c[0].get("data", ""))
        except: pass
if png3:
    with open(f"{OUT}/prop.png","wb") as f: f.write(png3)

# 清理
try:
    log("(X) mcp.stop...")
    mcp.stop()
except Exception as e:
    log(f" stop err: {e}")

log(f"DONE. 结果目录: {OUT}")
log(f"  goods_state=1 in 属性面板: {has}")
LOG.close()
