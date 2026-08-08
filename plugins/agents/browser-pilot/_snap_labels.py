#!/usr/bin/env python3
"""滚动计划编辑器页面，截取上游触发Tab完整视图 + 审计日志。"""
import sys, os, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
os.environ.setdefault("WSS_URL", "ws://127.0.0.1:9001/ws")
SCREENSHOTS_DIR = pathlib.Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)
from engine_adapter import BrowserPilot

def main() -> int:
    with BrowserPilot() as pilot:
        # --- 计划编辑器：点击「上游触发」Tab + 滚动
        print("=== 计划编辑器(上游触发) ===")
        pilot.navigate("http://127.0.0.1:5173/data/schedules")
        time.sleep(3.5)
        try:
            pilot.call_raw("browser_evaluate", {
                "expression": """() => {
                  // 找「上游触发」Tab 并点击
                  const tabs = [...document.querySelectorAll('button, div[role="tab"], a')];
                  const t = tabs.find(e => (e.innerText||'').includes('上游触发'));
                  if (t) t.click();
                  // 滚动到页面内容区
                  const panel = document.querySelector('.bp-cron-editor, main, section');
                  if (panel) panel.scrollIntoView({block:'start'});
                  window.scrollBy(0, 180);
                  return 'ok';
                }()"""
            })
            time.sleep(1.5)
        except Exception as e:
            print(f"  ⚠️  Tab/scroll: {e}")
        shot = pilot.screenshot(str(SCREENSHOTS_DIR / "13_schedules_upstream_trigger.png"))
        print(f"  📸 上游触发: 13_schedules_upstream_trigger.png")

        # --- 审计日志
        print("\n=== 审计日志 ===")
        pilot.navigate("http://127.0.0.1:5173/operations/audit")
        time.sleep(3.5)
        shot = pilot.screenshot(str(SCREENSHOTS_DIR / "12_audit_chinese_resource_ids.png"))
        print(f"  📸 审计日志: 12_audit_chinese_resource_ids.png")

        # --- 搭建页 BuildModal
        print("\n=== 搭建任务详情 ===")
        pilot.navigate("http://127.0.0.1:5173/data/builds/847")
        time.sleep(3.5)
        shot = pilot.screenshot(str(SCREENSHOTS_DIR / "14_build_job_chinese_name.png"))
        print(f"  📸 搭建任务: 14_build_job_chinese_name.png")

        print("\n🎉 4 个关键页面截图完成")
        return 0

if __name__ == "__main__":
    sys.exit(main())
