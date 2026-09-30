from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'plugins/browser/kitewright'))
from engine_adapter import BrowserPilot
root=Path(__file__).resolve().parent
with BrowserPilot(headless=True,kite_endpoint='http://127.0.0.1:8097/mcp') as pilot:
    assert pilot.navigate('http://127.0.0.1:8434/aip/model-runtime').success
    assert pilot.wait_for(selector='section[aria-label="创建网络审批提案"] button:disabled',timeout_ms=20000)
    pilot.click('role=button[name="查询原创建请求"]')
    assert pilot.wait_for(text='请填写精确网络策略 ID、候选修订和预期 head 版本',timeout_ms=10000)
    snapshot=pilot.snapshot()
    (root/'snapshot.txt').write_text(snapshot)
    data=pilot.screenshot(str(root/'current-form.png'),full_page=True)
    assert data
    print('empty_reference_validation_and_disabled_submit=True')
    print('screenshot_bytes',len(data))
