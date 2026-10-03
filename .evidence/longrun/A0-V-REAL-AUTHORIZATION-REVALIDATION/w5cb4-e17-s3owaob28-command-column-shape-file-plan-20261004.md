# E17-s3o-w-ao-b28｜Capability 命令精确列形状隔离施工方案

## 上位与当前证据

- 231-4 要求受控 INSERT/UPDATE 的表、列、谓词白名单和非 owner、FORCE RLS；BIND-1 31 要求版本 CAS、租户隔离、幂等 Receipt。b26/b27 disposable PG 已拒 version-only 假评估、状态/评估混写和同版本多 Receipt，但只检查若干列，不能排除在合法 update/evaluate 中夹带 `secret_ref` 等业务配置字段。
- 现有 `AipCapabilityBindingService.update` 只写 `status,health,observed_at,version,updated_at`；`evaluate` 只写 provider/model/runtime/eval/license/data/tool/budget 依赖、degraded、快照/readiness/原因/时间/版本。`create` 是新行。正式生产仍 `a0v_135`、当前库只读、写503，Host/worker/Provider关。

## 文件级计划

1. 仅在 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的 disposable full-schema DB test-only 守卫加两类 RED：合法状态转移同时改 `secret_ref` 并配 update Receipt；合法评估字段同时改 `secret_ref` 并配 evaluate Receipt；都必须拒绝。原 create/update/evaluate 与普通共享 Receipt 保持正向。
2. 最小修复只在 test-only BEFORE marker 中，对 UPDATE 比较除实际命令写列及 DB 派生 marker 外的 NEW/OLD JSONB；未许可列必须完全相同。update/evaluate 允许列分别按上方原 Store SQL 冻结；Binding deferred guard 仍验证 operation/一一 Receipt。禁止通过可写 session GUC 或 owner 角色冒充正式命令来源。
3. 专项与相邻五文件回归、py_compile/diff check、方案/代码复审、verification、m1精确提交与01/06/D-waves/Prime同步。若测试揭露 JSONB 比较绕过或 PostgreSQL 类型语义问题，先修方案。正式迁移、角色/凭据、历史行兼容和当前卷切换仍独立下一门，新 Alembic 头前须备份/全恢复/零执行窗口。

边界：原库只读，org-org/dev-project唯一正向，dev-org零副作用；不读商城源、不回放旧12Run、不手工run_definition、不碰230 L0、不 push。
