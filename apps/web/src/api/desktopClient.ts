/** 188m — desktop may publish client version for force-reject gate. */
let _desktopVersion: string | null = null;

export function setDesktopClientVersion(version: string | null): void {
  _desktopVersion = version && version.trim() ? version.trim() : null;
}

export function getDesktopClientVersion(): string | null {
  return _desktopVersion;
}
