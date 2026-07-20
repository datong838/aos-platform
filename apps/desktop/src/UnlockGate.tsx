/** 196m — unlock gate when requireUnlockOnResume is on */
import { unlockSession } from "./session";

export function UnlockGate({ onUnlocked }: { onUnlocked: () => void }) {
  async function onUnlock() {
    const ok = await unlockSession();
    if (ok) onUnlocked();
  }

  return (
    <div className="aos-desktop-welcome" data-ui="UI-196m-unlock">
      <h1>已锁定</h1>
      <p>本机已保存会话。开启「启动须解锁」后需确认再进入。</p>
      <div className="aos-desktop-welcome-actions">
        <button type="button" onClick={() => void onUnlock()}>
          解锁进入
        </button>
      </div>
    </div>
  );
}
