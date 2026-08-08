#!/usr/bin/env python3
"""_capture_final.py: 最终验收截图 — dataset not found 已修复。"""
import os, sys, time, json, threading, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = "/Users/ddt/work/projects/ai_agent/aos-platform/plugins/agents/browser-pilot/screenshots"
os.makedirs(OUT, exist_ok=True)

from engine_adapter import KitewrightMCP

FRONTEND_BASE = os.environ.get("AOS_WEB_BASE", "http://127.0.0.1:5173")

mcp = KitewrightMCP()
print("[final] 启动 kite...")
t = threading.Thread(target=mcp.start, daemon=True)
t.start(); t.join(timeout=30)
assert mcp._session_id, "session init failed"
print(f"[final] session={mcp._session_id}")

def call(tool, params, timeout_s=60):
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

# 1. 管道列表
print("[final] (1) 管道列表...")
call("browser_navigate", {"url": f"{FRONTEND_BASE}/data/pipelines"}, timeout_s=30)
time.sleep(5)
save_png(call("browser_screenshot", {"full_page": True}, timeout_s=30), "final_1_pipeline_list.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "final_1.txt"), "w", encoding="utf-8") as f:
    f.write(body)
print(f"  栖月汇 出现: {body.count('栖月汇')} 次")

# 2. P02 画布（重点：输出预览区域不应有 dataset not found）
print("[final] (2) P02 画布...")
call("browser_navigate", {"url": f"{FRONTEND_BASE}/data/pipelines/P02-product-qyh"}, timeout_s=30)
time.sleep(5)
save_png(call("browser_screenshot", {"full_page": True}, timeout_s=30), "final_2_p02_canvas.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "final_2.txt"), "w", encoding="utf-8") as f:
    f.write(body)
has_ds_error = "dataset not found" in body.lower()
print(f"  dataset not found 存在: {has_ds_error} (期望 False)")

# 3. P02 Source 属性面板
print("[final] (3) P02 Source 属性面板...")
for sel in ["text=source", "text=Source", "text=输入", "text=niushop"]:
    r = call("browser_click", {"selector": sel, "timeout_ms": 5000}, timeout_s=12)
    if isinstance(r, dict) and "error" not in r:
        print(f"  点击 {sel} 成功"); break
time.sleep(2)
save_png(call("browser_screenshot", {"full_page": True}, timeout_s=30), "final_3_p02_source_prop.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "final_3.txt"), "w", encoding="utf-8") as f:
    f.write(body)
print(f"  site_filter/goods_state 出现: {'goods_state' in body or 'site_filter' in body}")

# 4. P03 画布
print("[final] (4) P03 画布...")
call("browser_navigate", {"url": f"{FRONTEND_BASE}/data/pipelines/P03-product-sku-qyh"}, timeout_s=30)
time.sleep(5)
save_png(call("browser_screenshot", {"full_page": True}, timeout_s=30), "final_4_p03_canvas.png")
body = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "final_4.txt"), "w", encoding="utf-8") as f:
    f.write(body)
has_ds_error_p03 = "dataset not found" in body.lower()
print(f"  dataset not found 存在: {has_ds_error_p03} (期望 False)")

try: mcp.stop()
except Exception: pass
print(f"\n[final] 截图保存在: {OUT}")
print("  final_1_pipeline_list.png")
print("  final_2_p02_canvas.png")
print("  final_3_p02_source_prop.png")
print("  final_4_p03_canvas.png")
