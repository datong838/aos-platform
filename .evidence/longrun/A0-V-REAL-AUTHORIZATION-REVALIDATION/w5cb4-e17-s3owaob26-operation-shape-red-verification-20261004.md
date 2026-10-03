# E17-s3o-w-ao-b26｜operation 形状隔离 RED 与最小修复

## 方案与文件

- 文件级方案先于编码提交 `m1@d4c05124`；复习 231-4/BIND-1、b24/b25、`aip_registry_issuer_connection.py` 和三类 Capability Store SQL。本波只改 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 内一次性完整迁移测试库的 test-only SQL，未加生产迁移、未改 API 连接工厂或当前原库。
- 目标：版本递增不带评估快照不得生成 evaluate Receipt；状态变更与评估时间混写不得被归为 update；合法三类 Capability 与普通 Agent/Skill/Run/Handoff Receipt 保持可写。

## RED、最小修复与回归

1. 先加独立 issuer 的 version-only evaluate 负例；目标单项 `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py -k clone_only_capability_operation_guard_preserves_normal_receipts` exit1，`1 failed`，关键错误 `Failed: DID NOT RAISE InsufficientPrivilege`。与 b25 全恢复克隆的回滚 SQL 反例一致。
2. 仅把 test-only BEFORE marker 与 deferred Binding guard 的默认 evaluate 分支改成显式条件：`last_evaluated_at` 必变化且非空、`dependency_snapshot_hash` 非空、`readiness_expires_at > last_evaluated_at`；状态/health 改变与评估时间/快照哈希混写直接 `42501`。增加混写负例。目标单项 exit0，`1 passed, 1 deselected`。
3. 与 b24 相同的五文件相邻组 `-k 'not downgrade'` exit0，`14 passed, 1 deselected, 1 xfailed`。xfailed 是既有生产共享 Receipt 无配对写缺口；deselected 是在 `a0v_135` 禁止降级的旧测试。`python3 -m py_compile`、`git diff --check` exit0。测试文件原有终局断言仍要求试验 Receipt7/Binding1，说明新增负例没有留下持久行。

## 方案/代码复审与边界

修复仅证明 b24 隔离分类不再把 version-only/mixed 写当作合法命令；发行身份本身仍是 test-only，仍未验证历史 Binding、生产触发器、正式独立私有 issuer/OIDC、撤销、完整非法列矩阵。尤其只要 issuer 可同时伪造一套看似合法的评估字段，行形状不能单独证明业务来源；正式协议还需受控命令路径、精确列权限/可信来源和同事务 Receipt 约束。`a0v_136` 未进入 m1，当前权威库继续只读135，Capability 写503、Host/worker/Provider关，八配置/六 Binding/Owner/自然首链 pending。下一波 b27优先设计并隔离验证正式 operation 来源与非法列矩阵，不把本波测试 GREEN 作为正式发行或业务通过。
