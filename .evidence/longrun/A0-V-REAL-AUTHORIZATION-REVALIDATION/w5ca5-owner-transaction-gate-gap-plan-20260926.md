# W5ca5｜Fresh Owner 同事务关闭门代码/SQL 覆盖差距审计

## 上位与安全线

复习 231 A0-V 真实退休/direct successor、230 L0 挂起、W5c5g/W5c7t/W5ca4。原组十二 Run running、时间门过线但 Fleet/历史 row proof/Owner 门均不完整。本波仅静态和隔离既有测试证据分析；不得调用 `StalledSnapshotGroupClosureService.close`、SQL `pipeline_snapshot_stalled_group_close_a0v_091`、旧 W3/W4 `apply` 或真实 PG 写事务。

## 文件级审计清单

- `services/aos-api/alembic/versions/a0v_091_snapshot_stalled_group_closure.py`：逐项标明 SQL 同事务锁/资格/时间/Receipt/Run 更新；特别看 `meta_membership FOR SHARE` 与 actor 绑定、Host/Fleet token/lease 检查是否存在、idempotent replay 是否先于重新核实外部门。
- `services/aos-api/aos_api/pipeline_snapshot_stalled_group_closure.py`、`scripts/a0v_w3_stalled_group_close.py`、`scripts/a0v_w4_stalled_close.py`：服务事务边界、prepare/apply 冻结证据、未知提交和独立审计；不得把旧 W3/W4 成功挪作原组授权。
- 相关 `test_a0v_w5c4x/y/z_*`、`test_a0v_w5c6i_*`：现有隔离 PG 负例/成功范围及缺失的 Fleet/Host/Owner 原子绑定；本波不运行 PG 测试、不产生测试 DB。
- 形成“已具备/缺失/下一最小无效果验证”矩阵。若可安全推进，W5ca6 先方案实现一个默认拒绝、纯分类或隔离契约的最小包；若缺口完全依赖外部 Fleet authority，明确停止假工程。audit/verification/D-waves/AOS CAS/Prime 收口。

## 九步

1. 上位复习；2. 精确方案先提交；3. 静态 SQL/服务/脚本审；4. 隔离测试证据复核；5. 无新代码专项；6. 与原组 no-authority 自洽性；7. 8080 浏览器离线；8. 证据/记忆；9. 自动下一波。18181 仅本地诊断服务；租约到期责任仍在。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
