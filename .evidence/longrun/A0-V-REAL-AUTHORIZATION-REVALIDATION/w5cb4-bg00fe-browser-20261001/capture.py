from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4]/'plugins/browser/kitewright'))
from engine_adapter import BrowserPilot
root=Path(__file__).resolve().parent
with BrowserPilot(headless=True,kite_endpoint='http://127.0.0.1:8097/mcp') as pilot:
    page=pilot.navigate('http://127.0.0.1:8434/aip/drafts')
    assert page.success
    ready=pilot.wait_for(selector='[data-testid="drafts-empty"], [data-testid="canonical-action-inbox"] [role="alert"], [aria-label="执行提案详情"]',timeout_ms=20000)
    snapshot=pilot.snapshot()
    (root/'snapshot.txt').write_text(snapshot)
    data=pilot.screenshot(str(root/'current-inbox.png'),full_page=True)
    assert data, 'screenshot missing'
    print(snapshot[-6000:])
    print('terminal_ui_observed',ready)
    print('screenshot_bytes',len(data))
