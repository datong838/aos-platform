# Web human login integration

Rules:231,41-TX.3,132-TWC.3, original tenant/session API. Human approved local login and restoration; do not repeat approval.

Files: apps/web/src/App.tsx; apps/web/src/components/auth/LocalLoginGate.tsx; apps/web/src/api/passwordLogin.ts; apps/web/src/api/passwordLogin.test.ts.

Gate reads original GET /v1/auth/oidc without credentials. Legacy allowDevToken true retains existing routes. External-only config requires login before mounting business catalog/providers; missing config or unsupported password route shows retry/error, never silent dev fallback. Grant uses POST /v1/auth/token directly, no offline queue, no local/session storage for secrets or tokens. Verify canonical GET /v1/me with returned token and existing tenant scope; original backend verifier is authority, do not decode JWT or duplicate claims logic. Publish memory-only token and canonical tenant only after me succeeds; discard on failure. Password cleared immediately after submitted. No auto-resend, account bootstrap or business mutation. Reload requires login; refresh-token persistence deliberately not added.

RED/green covers exact original endpoints, no persistence, server canonical identity, failed or missing token and failed me, no offline replay. Build/typecheck and browser integration after new frozen API/Web deployment, not from current old source. Enrollment and eight runtime pages remain separate parent stages.

## Actual original interface correction
Live original POST returned200 on first real credential attempt. Original oidc.issue_password_token returns accessToken/refreshToken camelCase, same desktop TokenResponse. Initial Web mocked provider snake_case instead of original AOS envelope: tests missed contract mismatch. Correct original-envelope fixtures first for meaningful RED, then minimum client field correction; do not modify backend DTO or accept alternative invented formats. Preserve first live attempt evidence and reconcile its IdP session before a fresh independent acceptance.
