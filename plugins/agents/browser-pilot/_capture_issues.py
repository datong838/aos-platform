#!/usr/bin/env python3
"""_capture_issues.py: 针对 P02-product-qyh 的 3 个问题拍现场快照。
输出目录: /Users/ddt/work/projects/ai_agent/aos-platform/plugins/agents/browser-pilot/screenshots
"""
import os, sys, time, json, threading, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = "/Users/ddt/work/projects/ai_agent/aos-platform/plugins/agents/browser-pilot/screenshots"
os.makedirs(OUT, exist_ok=True)

from engine_adapter import KitewrightMCP

FRONTEND_BASE = os.environ.get("AOS_WEB_BASE", "http://127.0.0.1:5173")
PID = "P02-product-qyh"
URL = f"{FRONTEND_BASE}/data/pipelines/{PID}"

mcp = KitewrightMCP()
print("[capture] 启动 kite...")
t = threading.Thread(target=mcp.start, daemon=True)
t.start(); t.join(timeout=30)
assert mcp._session_id, "session init failed"
print(f"[capture] session={mcp._session_id}")

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
                b64 = item.get("data", "")
                with open(os.path.join(OUT, fname), "wb") as f:
                    f.write(base64.b64decode(b64))
                return True
    return False

def extract_text(resp):
    if isinstance(resp, dict) and "result" in resp:
        c = resp["result"].get("content", [])
        for item in c:
            if isinstance(item, dict) and "text" in item:
                return item["text"]
    return ""

# Step 1: 打开页面
print(f"[capture] (1) navigate {URL}")
call("browser_navigate", {"url": URL}, timeout_s=30)

# 等页面加载（用 snapshot 判断是否就绪）
print("[capture] 等待画布渲染...")
for _ in range(6):
    time.sleep(2)
    snap = call("browser_snapshot", {"diff": False}, timeout_s=15)
    txt = extract_text(snap)
    if "Builder" in txt or "画布" in txt or "Pipeline" in txt or "管道" in txt:
        print(f"  snapshot len={len(txt)}, 命中关键字 ✅"); break

# ===== 快照 A：画布全景（展示孤立 Transform 节点）=====
print("[capture] (A) 画布全景截图（展示孤立 Transform）...")
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "A_canvas_overview.png")
# 把画布 body 文字也存一下
body_txt = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "A_canvas_body.txt"), "w", encoding="utf-8") as f:
    f.write(body_txt)
# 把 snapshot 也存了
snap_txt = extract_text(call("browser_snapshot", {"diff": False}, timeout_s=15))
with open(os.path.join(OUT, "A_canvas_snapshot.txt"), "w", encoding="utf-8") as f:
    f.write(snap_txt)
print(f"  A_canvas_overview.png + A_canvas_body.txt + A_canvas_snapshot.txt")

# ===== 快照 B：点击 Source 节点 (niushop-qyh) 后属性面板 ======
print("[capture] (B) 点击 Source 节点 (niushop-qyh) ...")
for sel in ["text=niushop-qyh", "text=niushop", "text=Source", "aria=niushop-qyh"]:
    r = call("browser_click", {"selector": sel, "timeout_ms": 5000}, timeout_s=12)
    if isinstance(r, dict) and "error" not in r:
        print(f"  命中 {sel} ✅"); break
else:
    print("  ⚠️ 所有 selector 都没点中，继续")

time.sleep(2)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "B_source_prop_panel.png")
body_b = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "B_source_prop_body.txt"), "w", encoding="utf-8") as f:
    f.write(body_b)
print(f"  B_source_prop_panel.png + B_source_prop_body.txt")

# ===== 快照 C：点击 Transform 节点后属性面板 ======
print("[capture] (C) 点击 Transform 节点（含孤立变换 + 「Ingest」字样的）...")
for sel in ["text=变换", "text=Ingest", "text=Transform", "text=transform"]:
    r = call("browser_click", {"selector": sel, "timeout_ms": 5000}, timeout_s=12)
    if isinstance(r, dict) and "error" not in r:
        print(f"  命中 {sel} ✅"); break
else:
    print("  ⚠️ 没点中，继续")
time.sleep(2)
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "C_transform_prop_panel.png")
body_c = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "C_transform_prop_body.txt"), "w", encoding="utf-8") as f:
    f.write(body_c)
print(f"  C_transform_prop_panel.png + C_transform_prop_body.txt")

# ===== 快照 D：尝试点「试运行」按钮，捕获 validation failed 报错 ======
print("[capture] (D) 点击「试运行」/「部署并搭建」按钮，捕获 validation failed ...")
for sel in ["试运行", "部署并搭建", "run", "Run", "Deploy"]:
    r = call("browser_click", {"selector": sel, "timeout_ms": 3000}, timeout_s=10)
    if isinstance(r, dict) and "error" not in r:
        print(f"  命中 {sel} ✅")
        time.sleep(2)
        break
r = call("browser_screenshot", {"full_page": True}, timeout_s=30)
save_png(r, "D_after_run_click.png")
body_d = extract_text(call("browser_extract", {"selector": "body"}, timeout_s=20))
with open(os.path.join(OUT, "D_after_run_body.txt"), "w", encoding="utf-8") as f:
    f.write(body_d)
print(f"  D_after_run_click.png + D_after_run_body.txt")

# 清理
try: mcp.stop()
except Exception: pass
print(f"\n[capture] 所有产物已保存到: {OUT}")
