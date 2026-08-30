export type ExactResourceRef = {
  resourceType: string;
  resourceId: string;
  revision: string;
  authority: string;
};

const EXACT_PART = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/;
const POSITIVE_REVISION = /^[1-9][0-9]*$/;

function exactPart(value: string | null): string | null {
  const clean = String(value || "").trim();
  return EXACT_PART.test(clean) ? clean : null;
}

export function readExactRef(params: URLSearchParams, prefix: string, expectedType?: string): ExactResourceRef | null {
  const resourceType = exactPart(params.get(`${prefix}Type`));
  const resourceId = exactPart(params.get(`${prefix}Id`));
  const revision = String(params.get(`${prefix}Revision`) || "").trim();
  const authority = exactPart(params.get(`${prefix}Authority`));
  if (!resourceType || !resourceId || !POSITIVE_REVISION.test(revision) || !authority) return null;
  if (expectedType && resourceType !== expectedType) return null;
  return { resourceType, resourceId, revision, authority };
}

export function writeExactRef(params: URLSearchParams, prefix: string, ref: ExactResourceRef): URLSearchParams {
  const validated = readExactRef(new URLSearchParams({
    [`${prefix}Type`]: ref.resourceType,
    [`${prefix}Id`]: ref.resourceId,
    [`${prefix}Revision`]: ref.revision,
    [`${prefix}Authority`]: ref.authority,
  }), prefix);
  if (!validated) throw new Error(`Invalid exact ${prefix} reference`);
  params.set(`${prefix}Type`, validated.resourceType);
  params.set(`${prefix}Id`, validated.resourceId);
  params.set(`${prefix}Revision`, validated.revision);
  params.set(`${prefix}Authority`, validated.authority);
  return params;
}

export function safeLocalPath(value: string | null | undefined): string | null {
  const clean = String(value || "").trim();
  if (!clean.startsWith("/") || clean.startsWith("//") || /[\\\u0000-\u001f\u007f]/.test(clean)) return null;
  return clean;
}

export function readSafeReturnTo(params: URLSearchParams): string | null {
  return safeLocalPath(params.get("returnTo"));
}

export function buildExactContextHref(
  path: string,
  input: { params?: URLSearchParams; refs?: Record<string, ExactResourceRef | null | undefined>; cutoffAt?: string; returnTo?: string },
): string {
  const safePath = safeLocalPath(path);
  if (!safePath) throw new Error("Exact context target must be a local path");
  const [pathname, initialQuery = ""] = safePath.split("?", 2);
  const params = new URLSearchParams(initialQuery);
  input.params?.forEach((value, key) => params.set(key, value));
  Object.entries(input.refs || {}).forEach(([prefix, ref]) => { if (ref) writeExactRef(params, prefix, ref); });
  if (input.cutoffAt) {
    if (Number.isNaN(Date.parse(input.cutoffAt))) throw new Error("Invalid exact context cutoff");
    params.set("cutoffAt", new Date(input.cutoffAt).toISOString());
  }
  const returnTo = safeLocalPath(input.returnTo);
  if (returnTo) params.set("returnTo", returnTo);
  const query = params.toString();
  return `${pathname}${query ? `?${query}` : ""}`;
}
