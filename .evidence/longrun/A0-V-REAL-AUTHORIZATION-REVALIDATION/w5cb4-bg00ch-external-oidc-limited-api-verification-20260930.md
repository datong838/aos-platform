# W5CB4 BG00ch｜受限 API 外部 OIDC 禁开发身份验证

## 基线与 RED

AOS-000936、m1 `e18fbc65`、当前卷 `aos-a0v-recovery-pg-data` 的 `a0v_117` 当前库只读，09:00全栈重启已另留证。先复习231/231-4/231-5、现有 `oidc.py`/`auth.py` 与BG00cg启动器。`AOS_AUTH_ALLOW_DEV=0` 只挡字面 `Bearer dev`，旧 `verify_access_token` 仍能以默认开发 HS256 密钥验JWT，外部JWKS失败后会回落本地RSA。新增测试首次 RED 为4 failed/1 passed：开发HS256未被拒、JWKS失败本地回落、受限服务环境未强制正式门、缺外部配置未先阻断。

## 最小实现与回归

`oidc.py` 只在显式 `AOS_AUTH_EXTERNAL_ONLY=1` 下接受RS256/ES256且必须由已配置外部JWKS核验，失败直接拒绝；同时关闭字面dev与dev grant。默认开发配置不变。`a0v_current_preview_http.py --serve-limited` 要求非空 HTTPS 外部JWKS/issuer及显式audience，禁止loopback/内置默认，服务环境固定 `AOS_AUTH_ALLOW_DEV=0`、`AOS_AUTH_EXTERNAL_ONLY=1`、`AOS_REST_CONNECTOR_MOCK=0`。旧当前 `--serve` 服务路径不改。
正式模式的公开配置也仅在实际配置外部JWKS时显示 `jwksConfigured=true`，不再把本地开发JWKS冒充正式配置。

- 专项 `services/aos-api/.venv/bin/pytest -q services/aos-api/tests/test_oidc_external_only.py services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py --disable-warnings --tb=short`：11 passed，退出0。
- `python3.11 -m py_compile` 两实现文件与精确 `git diff --check`：退出0。
- 清除外部OIDC变量后直接执行 `--serve-limited`：退出2，`SAFE_BLOCKED/EXTERNAL_OIDC_CONFIG_REQUIRED`；没有接触当前数据库或启动第二服务。
- 相邻 `test_oidc_auth.py`、`test_auth.py`、两专项联合：16 passed/2 failed。两旧失败分别为旧测试 `org-b/prj-b` 当前workspace目录不存在而HTTP403、旧测试期望工作区名“测试工作区”而当前为“默认工作区”；单独重跑仍同样失败。新代码在未启用 external-only 时保留原 `allow_dev`/HS256/本地RSA分支；本波未修改租户目录或其预期。两失败登记为相邻基线漂移，不能声称累计全绿。
- 当前正式实例不具外部 OIDC 配置，也未创建受限API角色；当前API仍旧 `aos_app`，未用模拟IdP作正式验收。Host/worker/Provider、18181仍关闭；未写当前库、未读商城源、未回放Run。

## 边界与下一波

单元正例的 `_verify_jwks` 为隔离替身，只验证选择分支，不证明当前真实IdP可用。下一波先只读核真实外部OIDC authority/证书/issuer/audience/JWKS和栖月汇正式用户；若缺，具体实例保持禁入并推进网络Event发行者DB边界。受限API正式切换仍要独立备份、全链克隆、零执行窗口。第二真实checker/八配置/自然首链未完成。
