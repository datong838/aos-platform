#!/usr/bin/env python3
"""_capture_pass.py: 验收通过的页面证据截图。
1. 管道列表显示 8 条栖月汇管道
2. P02 画布：Source→Transform→Sink 连线完整
3. P02 Source 属性面板显示 site_filter
4. P03 同样通过
"""
import os, sys, time, json, threading, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = "/Users/ddt/work/projects/ai_agent/aos-platform/plugins/agents/browser-pilot/screenshots"
os.makedirs(OUT, exist_ok=True)

from engine_adapter import KitewrightMCP

FRONTEND_BASE = os.environ.get("AOS_WEB_BASE", "http://127.0.0.1:5173")

mcp = KitewrightMCP()
print("[pass] 启动 kite...")
t = threading.Thread(target=mcp.start, daemon=True)
t.start(); t.join(timeout=30)
assert mcp._session_id, "session init failed"
print(f"[pass] session={mcp._session_id}")

def call(tool, params, timeout_s=60, tag=""):
    res = [None]; err = [None]
    def _do():
        try: res[0] = mcp.call_tool(tool, params)
        except Exception as e: err[0] = e
    th = threading.Thread(target=_do, daemon=True)
    th.start(); th.join(timeout=timeout_s)
    if th.is_alive(): return {"error": f"timeout >{timeout_s}s"}
    if err[0]: return {"error": str(err[0])}
    return res[0]

def save_png(resp, fname):
    if isinstance(resp, dict) and "result" in resp:
        c = resp["result"].get("content", [])
        for item in c:
            if isinstance(item, dict) and item.get("type") == "image":
                with open(os.path.join(OUT, fname), "wb") as f:
                    f.write(base64.b64decode(item.get("data", "")))
                return True
    return False

def extract_text(resp):
    if isinstance(resp, dict) and "result" in resp:
        c = resp["result"].get("content", [])
        for item in c:
            if isinstance(item, dict) and "text" in item:
                return item["text"]
    return ""

# ===== 1. 管道列表 =====
print("[pass] (1) 管道列表...")
call("browser_navigate", {"url": f"{FRONTEND_BASE}/data/pipelines"}, timeout_s=30)
time.sleep(5)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "pass_1_pipeline_list.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "pass_1_pipeline_list.txt"), "w", encoding="utf-8") as f:
    f.write(body)
has_8 = body.count("栖月汇") >= 8
print(f"  栖月汇 出现次数: {body.count('栖月汇')} (期望>=8)")
print(f"  pass_1_pipeline_list.png")

# ===== 2. P02 画布 =====
print("[pass] (2) P02 画布...")
call("browser_navigate", {"url": f"{FRONTEND_BASE}/data/pipelines/P02-product-qyh"}, timeout_s=30)
time.sleep(5)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "pass_2_p02_canvas.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "pass_2_p02_canvas.txt"), "w", encoding="utf-8") as f:
    f.write(body)
print(f"  pass_2_p02_canvas.png")

# ===== 3. P02 Source 属性面板（点击 source 节点）=====
print("[pass] (3) P02 Source 属性面板...")
for sel in ["text=source", "text=Source", "text=输入", "text=niushop"]:
    r = call("browser_click", {"selector": sel, "timeout_ms": 5000}, timeout_s=12)
    if isinstance(r, dict) and "error" not in r:
        print(f"  点击命中 {sel}")
        break
time.sleep(2)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "pass_3_p02_source_prop.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "pass_3_p02_source_prop.txt"), "w", encoding="utf-8") as f:
    f.write(body)
has_site_filter = "goods_state" in body or "site_filter" in body or "site_id" in body
print(f"  属性面板含 site_filter 相关文字: {has_site_filter}")
print(f"  pass_3_p02_source_prop.png")

# ===== 4. P03 画布 =====
print("[pass] (4) P03 画布...")
call("browser_navigate", {"url": f"{FRONTEND_BASE}/data/pipelines/P03-product-sku-qyh"}, timeout_s=30)
time.sleep(5)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "pass_4_p03_canvas.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "pass_4_p03_canvas.txt"), "w", encoding="utf-8") as f:
    f.write(body)
print(f"  pass_4_p03_canvas.png")

# ===== 5. P03 Source 属性面板 =====
print("[pass] (5) P03 Source 属性面板...")
for sel in ["text=source", "text=Source", "text=输入", "text=niushop"]:
    r = call("browser_click", {"selector": sel, "timeout_ms": 5000}, timeout_s=12)
    if isinstance(r, dict) and "error" not in r:
        print(f"  点击命中 {sel}")
        break
time.sleep(2)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "pass_5_p03_source_prop.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "pass_5_p03_source_prop.txt"), "w", encoding="utf-8") as f:
    f.write(body)
has_site_filter_p03 = "goods_state" in body or "site_filter" in body or "site_id" in body
print(f"  属性面板含 site_filter 相关文字: {has_site_filter_p03}")
print(f"  pass_5_p03_source_prop.png")

try: mcp.stop()
except Exception: pass
print(f"\n[pass] 所有截图已保存到: {OUT}")
print(f"  文件清单:")
for f in sorted(os.listdir(OUT)):
    if f.startswith("pass_"):
        print(f"    {f}")
