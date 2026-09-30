# W5CB4 BG00ch｜受限 API 正式外部 OIDC 身份门

## 上位合同与缺口

复习 231 主计划、231-4 数据权限、231-5 审批/恢复，BG00cg 受限启动器与当前 `auth.py`/`oidc.py`。`--serve-limited` 已可限制 DB login，但当前 `AOS_AUTH_ALLOW_DEV=0` 只拒绝字面 `Bearer dev`；`verify_access_token` 仍接受默认 HS256 开发密钥签出的 JWT，JWKS 失败后还会尝试本地开发 RSA JWKS。若据此切换正式 API，会让假账号穿过应用身份边界。

## 文件级计划

1. `services/aos-api/aos_api/oidc.py` 增加显式 `AOS_AUTH_EXTERNAL_ONLY=1` 分支：拒绝 HS256/本地开发签发；只接受配置的外部 JWKS 对 RS256/ES256 的成功验证，失败不得回落本地 JWKS。默认开发分支保持原有行为，避免影响当前旧服务。
2. `scripts/a0v_current_preview_http.py` 的 `--serve-limited` 设置 `AOS_AUTH_ALLOW_DEV=0`、`AOS_AUTH_EXTERNAL_ONLY=1`、`AOS_REST_CONNECTOR_MOCK=0`，并在启动前 fail-closed 检查非空外部 JWKS/正式 issuer/audience，不允许内置开发默认值。旧 `--serve` 路径不改；当前无正式 OIDC authority 时不切换。
3. `services/aos-api/tests/test_oidc_external_only.py` 与 `tests/extension_runtime/test_a0v_current_preview_http.py` 先 RED：开发 HS256 JWT、字面 dev、外部 JWKS失败本地回落、缺配置启动均应拒绝；配置完整且外部验证成功的既有认证路径继续可用。再最小代码、专项与邻近回归。克隆验证仅限身份/只读，不造正式 checker 或批准。
4. verification、续接与 D-waves、精确 m1 提交、authority/Prime 同步。之后单独备份/克隆/零执行窗口推进当前受限 API 角色与服务切换；网络 Event 发行者及不变性 DB 门下一波。

## 停线

当前真实库只读、18181/Host/worker/Provider 关闭。开发密钥或本地 JWKS 不能替代正式身份。无外部 OIDC 配置时正式受限服务须阻断，不能回退 `aos_app` 高权路径声称通过。不可用 test mock、dev-org canary、手工 Run、旧12 Run 回放。
