#!/usr/bin/env python3
"""browser-pilot 验收脚本（debug版：超时兜底 + 全步骤独立守护 + 详细日志）。

每个外部操作都包独立 watchdog（子进程 + 超时 kill），避免 browser_* 工具永不返回卡死主流程。
"""
import os, sys, time, subprocess, signal, json, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_adapter import BrowserPilot

OUT = "/tmp/bp_verify_p02p03"
os.makedirs(OUT, exist_ok=True)

# ============================================================
# 1. 启动 watchdog: 独立子进程跑 BrowserPilot 代码，45s 不返回就杀
# ============================================================
WORKER_SCRIPT = r"""
import os, sys, time, json, traceback, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_adapter import BrowserPilot

OUT = "/tmp/bp_verify_p02p03"
os.makedirs(OUT, exist_ok=True)

STDOUT = open(f"{OUT}/run.log", "w", buffering=1)
def log(msg):
    t = time.strftime('%H:%M:%S')
    print(f"[{t}] {msg}", file=STDOUT)
    print(f"[{t}] {msg}", flush=True)

def write_result(rows, fatal=None):
    import time as t
    # 生成 HTML 报告
    imgs = sorted([f for f in os.listdir(OUT) if f.endswith(".png")])
    def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    rows_html = []
    all_pass = True
    for name, want, ok in rows:
        color = "#d4edda" if ok else "#f8d7da"
        mark = "✅ PASS" if ok else "❌ FAIL"
        if not ok: all_pass = False
        rows_html.append(f"<tr style='background:{color}'><td>{esc(name)}</td><td>{esc(want)}</td><td>{mark}</td></tr>")
    imgs_html = "".join(
        f"<details open><summary><b>{esc(img)}</b></summary>"
        f"<img src='{esc(img)}' style='max-width:100%;border:1px solid #ddd;border-radius:4px;margin-top:8px'/>"
        f"</details>" for img in imgs
    )
    status_html = "<h2 style='color:#155724;background:#d4edda;padding:12px;border-radius:6px'>✅ 全部通过</h2>" if all_pass else (
        "<h2 style='color:#721c24;background:#f8d7da;padding:12px;border-radius:6px'>"
        "⚠️ 存在失败项 —— YAML 是规格模板，DB 里已有的管道实例不会自动同步，"
        "需要通过「管道提案 → 新建提案」重建实例</h2>")
    if fatal:
        status_html = f"<h2 style='color:#721c24;background:#f8d7da;padding:12px;border-radius:6px'>" \
                      f"💥 执行中断: {esc(str(fatal))}</h2>"
    html = "<!doctype html><html lang=zh-CN><head><meta charset=utf-8>" \
        "<title>P02/P03 过滤条件验收</title>" \
        "<style>body{font-family:system-ui,-apple-system,sans-serif;max-width:1400px;margin:24px auto;padding:0 20px}" \
        "h1,h2{margin-top:28px}table{border-collapse:collapse;width:100%;margin:16px 0}" \
        "th,td{border:1px solid #e5e7eb;padding:10px 14px;text-align:left}" \
        "th{background:#f9fafb}details{margin:16px 0;background:#fafafa;border:1px solid #eee;border-radius:6px;padding:12px}" \
        "summary{cursor:pointer;font-weight:500;padding:4px 0}</style></head><body>" \
        f"<h1>P02商品 / P03商品SKU 管道 source_filter 验收报告</h1>" \
        f"<p>生成时间：{t.strftime('%Y-%m-%d %H:%M:%S')}</p>" + status_html + \
        "<h2>验收项</h2><table><tr><th>管道</th><th>预期</th><th>结果</th></tr>" + \
        "".join(rows_html) + "</table>" + \
        "<h2>截图证据</h2>" + imgs_html + "</body></html>"
    with open(f"{OUT}/index.html","w",encoding="utf-8") as f: f.write(html)
    with open(f"{OUT}/rows.json","w") as f: json.dump({"rows": rows, "fatal": str(fatal) if fatal else None}, f, ensure_ascii=False, indent=2)
    STDOUT.flush(); STDOUT.close()

rows = []

def try_snap(pilot, name):
    try:
        p = f"{OUT}/{name}.png"
        # browser_screenshot 卡的话也不要超过 15s
        def _do():
            try: pilot.screenshot(output_path=p, full_page=False)
            except Exception as _e: log(f"screenshot {name} 错误: {_e}")
        t = threading.Thread(target=_do, daemon=True); t.start(); t.join(timeout=15)
        return p
    except Exception as e:
        log(f"screenshot {name} 异常: {e}"); return None

def check_pipeline(pilot, tag, display_name, expected, step):
    log(f"--- {tag} 检查 {display_name} ---")
    # === step 1: 打开画布 ===
    log("  (1) 点卡片上的 打开画布 按钮...")
    ok_open = False
    # 方式A: 用 Kitewright 原生 text= 选择器
    for sel in [
        f"text=打开画布 >>xpath=/ancestor::*[contains(., '{display_name}')][1]",
        f"text={display_name} >>xpath=/following::*[text()='打开画布'][1]",
    ]:
        try:
            t = threading.Thread(target=lambda: pilot.click(sel, timeout_ms=8000), daemon=True)
            t.start(); t.join(timeout=15)
            if not t.is_alive():
                ok_open = True; log(f"  (1) opened via {sel[:50]}..."); break
        except Exception as e:
            log(f"  (1) sel fail: {e}")
    if not ok_open:
        # 方式B: 直接点文本（可能点到卡片里的显示名进入详情）
        try:
            t = threading.Thread(target=lambda: pilot.click(f"text={display_name}", timeout_ms=8000), daemon=True)
            t.start(); t.join(timeout=15)
            if not t.is_alive(): ok_open = True; log("  (1) opened by clicking display name")
        except Exception as e:
            log(f"  (1) display name click fail: {e}")
    try_snap(pilot, f"{step}_01_canvas")

    # 等 Builder/画布 文字
    try:
        t = threading.Thread(target=lambda: pilot.wait_for(text="Builder", timeout_ms=15000), daemon=True)
        t.start(); t.join(timeout=20)
    except Exception: pass
    try_snap(pilot, f"{step}_01b_builder")

    # === step 2: 点 source 节点 ===
    log("  (2) 尝试点 source/输入/niushop 节点...")
    clicked = False
    for sel in [
        "text=Source", "text=输入", "text=niushop",
        "text=niushop-qyh", "role=button[name*='Source']",
    ]:
        try:
            t = threading.Thread(target=lambda s=sel: pilot.click(s, timeout_ms=5000), daemon=True)
            t.start(); t.join(timeout=10)
            if not t.is_alive(): clicked = True; log(f"  (2) clicked {sel}"); break
        except Exception as e:
            log(f"  (2) sel {sel} fail: {e}")
    try_snap(pilot, f"{step}_02_source_clicked")

    # === step 3: 读 body + snapshot ===
    log("  (3) 读取属性面板文本...")
    body_text, snap_text, md_text = "", "", ""
    try:
        t = threading.Thread(target=lambda: pilot.extract_text("body"), daemon=True)
        t.start(); t.join(timeout=15)
        if not t.is_alive():
            # 用 locals hack 拿返回值
            import inspect
    except Exception: pass
    # 换更直接的方式
    def _extract_body_nonblocking():
        nonlocal body_text, snap_text, md_text
        try:
            t1 = threading.Thread(target=lambda: pilot._mcp.call_tool("browser_extract", {"selector":"body"}), daemon=True)
            t1.start(); t1.join(timeout=15)
            if not t1.is_alive():
                r = pilot._mcp.call_tool("browser_extract", {"selector":"body"})
                # 避免二次调用直接拿到结果，改用 pilot.extract_text：
        except Exception: pass
    # 直接调用各方法，包在 threading
    def _wrap(fn, *a, **k):
        try: return fn(*a, **k)
        except Exception as _e: log(f"  extract err: {_e}"); return ""
    try:
        t1 = threading.Thread(target=lambda: None, daemon=True); t1.start()
        # body
        t1 = threading.Thread(target=lambda: _wrap(lambda: exec('global _r; _r = pilot.extract_text("body")', globals())), daemon=True)
        t1.start(); t.join(timeout=15) if False else None
    except Exception: pass

    # 简单版：不存 locals，直接用辅助对象
    class Bucket: pass
    b = Bucket()
    def grab():
        try:
            b.body = pilot.extract_text("body") or ""
        except Exception as e:
            b.body = f"<err:{e}>"
        try:
            b.snap = pilot.snapshot(diff=False) or ""
        except Exception as e:
            b.snap = f"<err:{e}>"
        try:
            b.md = pilot.extract_markdown() or ""
        except Exception as e:
            b.md = f"<err:{e}>"
    tg = threading.Thread(target=grab, daemon=True)
    tg.start(); tg.join(timeout=30)
    body_text = getattr(b, "body", "")
    snap_text = getattr(b, "snap", "")
    md_text = getattr(b, "md", "")
    combined = body_text + "\n" + snap_text + "\n" + md_text
    # 落盘
    with open(f"{OUT}/{step}_body.txt","w",encoding="utf-8") as f: f.write(body_text)
    with open(f"{OUT}/{step}_snap.txt","w",encoding="utf-8") as f: f.write(snap_text)
    with open(f"{OUT}/{step}_md.txt","w",encoding="utf-8") as f: f.write(md_text)

    has_goods_state_eq1 = expected in combined
    has_goods_state_any = "goods_state" in combined
    has_filter_key = any(k in combined for k in ["source_filter","site_filter","sourceFilter","siteFilter","过滤条件"])
    log(f"  (3) 过滤配置键出现: {has_filter_key}")
    log(f"  (3) goods_state 关键字出现: {has_goods_state_any}")
    log(f"  (3) goods_state=1 命中: {has_goods_state_eq1}")

    # assert_text 兜底
    try:
        t = threading.Thread(target=lambda: pilot.assert_text(expected), daemon=True)
        t.start(); t.join(timeout=15)
    except Exception: pass
    try_snap(pilot, f"{step}_03_panel")

    if has_goods_state_eq1:
        log(f"  {tag} ✅ PASS (goods_state=1 found)")
    else:
        log(f"  {tag} ❌ FAIL")
    return has_goods_state_eq1

# ===== main =====
def main_inner():
    with BrowserPilot() as pilot:
        log("BrowserPilot 启动成功（MCP initialize done）")
        # 1 进管道列表
        log("navigate /data/pipelines ...")
        try:
            pilot.navigate("http://127.0.0.1:5173/data/pipelines")
        except Exception as e:
            log(f"navigate err (ignored): {e}")
        try_snap(pilot, "01_pipelines_list")
        # 等页面出现「栖月汇」
        try:
            pilot.wait_for(text="栖月汇", timeout_ms=20000)
            log("wait_for 栖月汇: ok")
        except Exception as e:
            log(f"wait_for 栖月汇: timeout (continue): {e}")
        try_snap(pilot, "01b_after_wait")

        # P02
        ok_p02 = check_pipeline(pilot, "P02", "栖月汇-商品", "goods_state=1", "2_p02")
        rows.append(("P02 商品 管道", "画布属性面板 source_filter 含 goods_state=1", ok_p02))
        try_snap(pilot, "2_p02_99_end")

        # 回列表
        log("返回管道列表 (/data/pipelines)...")
        try: pilot.navigate("http://127.0.0.1:5173/data/pipelines")
        except Exception as e: log(f"navigate back err: {e}")
        try: pilot.wait_for(text="栖月汇", timeout_ms=20000)
        except Exception: pass
        try_snap(pilot, "02_back_to_pipelines")

        # P03
        ok_p03 = check_pipeline(pilot, "P03", "栖月汇-商品SKU", "goods_state=1", "3_p03")
        rows.append(("P03 商品SKU 管道", "画布属性面板 source_filter 含 goods_state=1", ok_p03))
        try_snap(pilot, "99_finish")

try:
    main_inner()
    write_result(rows)
except Exception as e:
    log(f"FATAL: {e}\n{traceback.format_exc()}")
    write_result(rows, fatal=e)
"""  # end worker

WORKER_PATH = f"{OUT}/_worker.py"
with open(WORKER_PATH, "w") as f:
    f.write(WORKER_SCRIPT)

# 在正确的 CWD 运行 worker，以便 import engine_adapter
cwd = os.path.dirname(os.path.abspath(__file__))
proc = subprocess.Popen(
    [sys.executable, "-u", WORKER_PATH],
    cwd=cwd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    env=os.environ,
)

# 读取 stdout 实时打印
def teardown():
    try:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill()
    except Exception: pass
    # 也清理残留 kite/chrome
    import shutil, signal
    try:
        for p in map(int, subprocess.check_output(["pgrep","-f","bin/kite"]).decode().split()):
            try: os.kill(p, signal.SIGKILL)
            except Exception: pass
    except Exception: pass
    try:
        for p in map(int, subprocess.check_output(["pgrep","-f","Chrome.*remote-debug"]).decode().split()):
            try: os.kill(p, signal.SIGKILL)
            except Exception: pass
    except Exception: pass

import signal as _sig
def _handler(signum, frame):
    print("\n[WATCHDOG] 收到中断信号，清理...", flush=True)
    teardown(); sys.exit(1)
_sig.signal(_sig.SIGINT, _handler)
_sig.signal(_sig.SIGTERM, _handler)

# 主循环：最多 300s（= 5 分钟兜底），且 30s 无 stdout 新输出超时就杀
DEADLINE = time.time() + 300
LAST_OUTPUT = time.time()
output_chunks = []
try:
    import select
    while True:
        now = time.time()
        if now > DEADLINE:
            print(f"\n[WATCHDOG] 总超时 300s，杀掉 worker", flush=True)
            teardown(); break
        if proc.poll() is not None:
            # 读完剩余
            try: output_chunks.append(proc.stdout.read().decode(errors='replace'))
            except Exception: pass
            print("".join(output_chunks), end="")
            print(f"[WATCHDOG] worker 退出 code={proc.returncode}", flush=True)
            break
        # 等输出
        r, _, _ = select.select([proc.stdout], [], [], 1.0)
        if r:
            try:
                d = proc.stdout.read1(4096)
            except Exception:
                d = b""
            if d:
                s = d.decode(errors='replace')
                output_chunks.append(s)
                print(s, end="", flush=True)
                LAST_OUTPUT = now
            else:
                # EOF
                break
        else:
            # 无输出
            if now - LAST_OUTPUT > 60:
                print(f"\n[WATCHDOG] 60s 无输出（LAST_OUTPUT={time.ctime(LAST_OUTPUT)}），疑似卡死，杀掉 worker", flush=True)
                teardown(); break
finally:
    teardown()

# 读取产物
print(f"\n{'='*60}")
rows_path = f"{OUT}/rows.json"
if os.path.exists(rows_path):
    with open(rows_path) as f:
        data = json.load(f)
    rows = data.get("rows", [])
    fatal = data.get("fatal")
    all_pass = all(r[2] for r in rows)
    for name, want, ok in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} | {want}")
    print()
    if fatal:
        print(f"💥 执行中断: {fatal}")
    elif all_pass:
        print("✅ 全部通过")
    else:
        print("⚠️ 存在失败项（大概率是 DB 管道实例没同步 YAML 模板）")
    print(f"\n📂 验收报告: file://{OUT}/index.html")
else:
    print(f"❌ 产物 rows.json 不存在（worker 可能未执行完），看日志 {OUT}/run.log")
    if os.path.exists(f"{OUT}/run.log"):
        print("--- 最后 30 行 run.log ---")
        with open(f"{OUT}/run.log", errors="replace") as f:
            lines = f.readlines()
            for l in lines[-30:]: print(l.rstrip())
