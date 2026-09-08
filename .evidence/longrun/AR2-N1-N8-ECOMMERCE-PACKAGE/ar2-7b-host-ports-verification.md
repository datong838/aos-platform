# AR2-7B 宿主端口禁入基线验收证据

- 验收时间：2026-09-08T11:19:36+08:00
- 分支：`m1`
- 源提交：`c8c0e95d5d0cc1eb55c31bbe0c418b1d9ae4f339`
- 方案提交：`06fb9df3ed14ba32b460f0f306d16c764d6a5f15`
- 结果：`AR2_7B_SEALED_HOST_PORTS_REGISTRATION_ONLY_GREEN`

## 闭合范围

1. 每次提交均在串行事务中锁定完整 cutover group，并精确复核 DispatchRef、Installation、generation、epoch、fence 与 runtime ready 状态。
2. 命令只接受严格 JSON tree；拒绝租户、dispatch、Secret、Provider URL、SQL 和自报授权结论，合法审批精确引用交由后续运行 adapter 重验。
3. 固定九类 operation、authority kinds 与目标 Receipt keys；生产 composition 不接受 callback mapping。
4. AR2-7D 接线前九类端口统一返回 `AR2_7D_RUNTIME_WIRING_REQUIRED`，不写领域数据、不制造回执。
5. 测试专用底层 binding 只验证事务框架；当前生产代码仅 composition 引用宿主端口，Router 尚无可达旁路。

## 验证结果

- 宿主端口纯专项：`25 passed`。
- PostgreSQL 事务／RLS 专项：`3 passed`。
- AR1 runtime、N1～N7、预算合同累计回归：`191 passed`。
- Python 编译、精确 `git diff --check`：通过。
- Alembic：唯一 head `ar2_003`。
- 独立 Prime：`PASS`，无确定性 blocker。

## 文件摘要

- `ecommerce_growth_host_ports.py`: `sha256:35dc5d5bee11701f69cc3642a81d540fc3c691f17b3c664b671b99020b433fa6`
- `ecommerce_growth_host_composition.py`: `sha256:9eed55f1dbb5652bd8f185e9c3ca4002ce58f8da3c454b406e26a647ffce03f4`
- `test_ecommerce_growth_host_ports.py`: `sha256:938c914248e2b815936c90c9ba9e8b67be7e8bf85432ef77f6ba9b4e4da1e28a`
- `test_ecommerce_growth_host_ports_pg.py`: `sha256:9ac7916399c1d06afa08cfbd7262bcb54db59c5110daf97578433a1499249ce5`

## 安全边界与下一步

- 未启用真实租户、未解析 Secret、未调用 Provider、未修改经营数据、未发布、未产生费用。
- 本证据只封板 AR2-7B 通用事务与禁入基线；真实 authority reader、领域 executor、Receipt 数据库回读和 Canonical Router 单写接线仍由 AR2-7D 闭合。
- 自动进入 AR2-7C：实现内容评审结果回流、总控复盘、AI 改进建议、Wiki 候选与可恢复 outbox。
