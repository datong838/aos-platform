# E17-s3o-w-ao-b22｜Capability 共享 Receipt 发行合同验证

## 范围与前提

- 上位依据：231-4/BIND-1、b12 Tool 独立发行探针、b19 Capability 无配对 Receipt 负证据、b22 文件级计划（`m1@6a5657fa`）。
- 仅在 pytest 一次性全迁移 `aos_test_*_ti4_test` 数据库建随机非 owner `NOINHERIT` LOGIN、租户 RLS、最小 ACL 与 test-only 触发器。测试收尾删除这些对象；当前权威卷/库只读，生产代码、API/Web、Host/worker/Provider 均未改动。
- 正向租户只有 `org-org/dev-project`；`dev-org` 仅用作拒绝跨租户写入的 canary。无商城源读取、旧 Run 回放或手工 Run。

## RED 与隔离正反证明

1. 首次单跑 `AOS_DOTENV_DISABLED=1 uv run pytest -q --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py`：exit 1、`1 failed`；独立 runtime 登录可直接插入无 Binding 的 `capability_binding.create` Receipt，未抛 `InsufficientPrivilege`。该缺口保留为 strict xfail。
2. 只在测试库加 `SECURITY INVOKER` Receipt 守卫及 deferred Binding 反查：精确发行 `session_user`、三种 Capability operation、同租户、结果 Binding ID/版本与当前事务行版本相配；issuer 普通 operation 和 runtime Capability 伪造均拒绝。普通 runtime `agent_instance.create` Receipt 正向保留。`SET ROLE` 提权拒绝。正向 create/update/evaluate 版本 1/2/3 同事务通过；无配对、无 Receipt Binding、旧事务补发、错版本、跨租户、重复、回滚均拒绝或不留行。最后只留下 4 条 test-only Receipt（含一条普通操作）、1 条 Binding，并由测试库销毁。
3. 相邻回归命令：`AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob12_tool_receipt_identity_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py`，exit 0，`6 passed, 1 xfailed, 7 warnings in 4.80s`。首次重复回执负例预期为 `UniqueViolation`，实际先由本波触发器以 `CAPABILITY_RECEIPT_UNPAIRED` 拒绝；改按实际安全结果断言后复跑 GREEN。
4. `python3 -m py_compile services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` exit 0；`git diff --check` exit 0。

## 方案/代码一致性与未关闭风险

- 本波实现的是隔离证明，不是生产迁移。原 `AipAgentRegistryStore._ref()` 将 `ResourceRef.revision` 固定为 `None`；本波 test-only 正向显式传版本，仅能证明精确配对协议在独立身份下可行，不能声称原 Store 已满足合同。
- `xmin` 与当前事务 ID 仅作一次性数据库探针；正式持久合同仍须明确 Binding 版本来源、Receipt 结果版本、精确发行身份/撤销、完整合法 operation 兼容、迁移回滚与原卷零执行窗口。原共享 Receipt INSERT 权限不可整体撤掉，否则 Agent/Skill/Run 等合法路径受损。
- 当前预览五类 Capability 写由 b20 继续 503 禁入。正式 OIDC/API 非 owner、Reader/issuer 当前角色及私有凭据、八配置、六 Binding、Host assignment/Owner 与自然首链未由本波证明。浏览器验收不适用于本波仅测试库改动；最近生产浏览器证据仍是 b20 三阻断/禁用。

## 下一波入口

先核当前 `result_ref.revision`/Binding 版本持久合同与现有普通 operation 的 Receipt 兼容矩阵；在独立 test DB 写原 Store 的正反 RED，再决定最小生产代码及安全迁移方案。若正式身份或公共协议尚需裁决，转已登记的八配置/六 Binding 独立代码项；不放宽当前写门。
