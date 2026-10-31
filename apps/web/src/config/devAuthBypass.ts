/** Dev/test: skip LocalLoginGate UI. Login code stays; set VITE_AOS_SKIP_LOGIN_GATE=0 to re-enable. */
export function isLoginGateSkipped(): boolean {
  const v = import.meta.env.VITE_AOS_SKIP_LOGIN_GATE;
  if (v === "0" || v === "false") return false;
  if (v === "1" || v === "true") return true;
  return import.meta.env.DEV;
}
