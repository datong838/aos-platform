/** Client-side mirror of C-ID-01 for UI guard before publish. */
export function lintClientSideId(id: string): { ok: boolean; reason?: string } {
  if (!id) {
    return { ok: false, reason: "id required" };
  }
  if (!/^[A-Z][A-Za-z0-9_]*$/.test(id)) {
    return { ok: false, reason: "id must be PascalCase alphanumeric" };
  }
  return { ok: true };
}
