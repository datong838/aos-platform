# W5c8r｜见证写门剩余拒绝矩阵与离线部署前审计

## 上位与当前边界

承接 W5c8q `m1@7c609e6e`/AOS-000679。`a0v_098` 只在一次性隔离 PG 测试安装；真实 `aos-extension` profile 停止，真实库未迁 096–098，原 12 Run/Receipt 当前状态未读回。本波先补单函数/双角色的数据库拒绝矩阵与离线部署前审计，不启真实 profile、不迁真实库、不授 operator、不扫商城源或真实历史。

## 文件级清单

- 复习 `a0v_045/097/098`、W5c8q verification 与上位 Host/Delivery/unknown 冻结门；对照 current m1、隔离 PG、依赖于完整原保存组的测试工厂。
- 扩展 `services/aos-api/tests/extension_runtime/test_a0v_w5c8q_witness_backfill_gate_pg.py` 或新增聚焦测试：错误角色/无显式 SET ROLE、超权 session、可写隔离级别错误、缺 GUC/跨租户、缺 input、canonical 文本/hash 漂移、actor/member 漂移、同键异值/并发；数据库不可变约束无法构造的负例明确标记为未证，不以 mocks 代替。
- 如测试揭示缺陷，先修订本方案，再最小调整 `services/aos-api/alembic/versions/a0v_098_snapshot_group_witness_backfill_gate.py`；已提交 migration 的后续改动必须解释“真实库从未迁”的条件，若存在任何可能已迁的证据立即停止改旧 migration，改新修复 migration。
- 离线审计只读检查 migration DAG、角色/函数 grant、调用方代码引用、目标环境仍停止；不得把离线审计当真实 DB 授权。

## 九步

1. 复习方案、产品和真实冻结门/HEAD。
2. 本方案提交。
3. 先 RED 完整隔离 PG 拒绝负例。
4. 如必要最小实现修复；否则仅测试与审计。
5. 专项/累计、角色/数据库残留 0、静态检查。
6. 无新增 UI，浏览器仅只读可达性，不能宣称真实验收。
7. 权限/哈希/并发/部署一致性复审。
8. verification、m1/D-waves/AOS CAS/Prime。
9. 自动 W5c8s：在所有前置证据齐全时设计真实 profile 只读重启与 migration canary 顺序；若仍缺证据先补专项，不实际操作真实库。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
