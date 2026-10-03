# E17-s3o-w-ao-b28｜Capability 命令精确列形状隔离验证

## 方案先行与 RED

- 上位 231-4/BIND-1、b26/b27 及原 `AipCapabilityBindingService.update/evaluate` SQL 复习后，文件级方案 `m1@127fbc1f` 先提交；只修改 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 disposable full-schema PG test-only BEFORE marker，不增加正式 Alembic 或 API 代码。
- 新负例：issuer 做合法 status update 同时夹带 `secret_ref` 改写并发 update Receipt；另一例做合法评估时间/有效期更新同时夹带 `secret_ref` 并发 evaluate Receipt。目标单项原测试 exit1，`1 failed`，关键 `Failed: DID NOT RAISE InsufficientPrivilege`。

## 最小修复与验证

- test-only BEFORE marker 对 UPDATE 的 `to_jsonb(NEW/OLD)` 删去原 Store 允许的精确列及数据库派生 marker 后作差异比较；update 只允许 status/health/observed_at/version/updated_at，evaluate 只允许原服务列出的依赖、degraded、快照/readiness/原因/评估时间与有效期/version/updated_at。夹带 `secret_ref` 等非命令列抛 `42501`。原 b26 评估形状与 b27 同版本一一配对约束保持。
- 目标单项 exit0，`1 passed, 1 deselected`；五文件相邻组 `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_aip6_003_exact_instance.py tests/aip/test_aip6_capability_run_handoff.py -k 'not downgrade'` exit0，`14 passed, 1 deselected, 1 xfailed`。xfailed 是原生产共享 Receipt 无配对缺口，deselected 是135不可降级旧测试。`py_compile` 与 `git diff --check` exit0。
- 当前权威库 `BEGIN READ ONLY` 后读135/Binding0/Receipt6，未写；当前 Capability 写503，Host/worker/Provider关。本波无生产运行逻辑变更，浏览器和重启不适用。

## 复审与下一门

JSONB 比较仅在 test-only 守卫验证 UPDATE 的非法列；正式 issuer 身份/凭据、CREATE 的字段及来源、DB trigger 禁用权限、历史行/全库恢复、受控命令来源仍未封。尤其一个持有 issuer 身份的调用者仍可伪造一套合法形状的评估字段；行形状不是业务来源证明。下一波先对 CREATE/issuer 能力和受控 operation 来源做独立 RED，生产迁移与当前卷切换保持独立安全门。不 push、不读商城源、不碰旧12Run/230 L0。
