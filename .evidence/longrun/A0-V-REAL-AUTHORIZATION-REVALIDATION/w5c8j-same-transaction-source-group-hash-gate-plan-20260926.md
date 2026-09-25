# W5c8j｜同事务源组 canonical hash 门禁计划

## 上位约束与目标

承接 W5c8h 审计、W5c8i `m1@5bceedd4`/AOS-000671。旧 unknown SQL 入口只在隔离 PG head 被撤权，真实库尚未迁移；新受控入口尚不存在。完整正向对账必须在单个 `aos_runtime` 写事务内先 `a0v_094` Host fence，再按固定 Host→Delivery 锁序重核原 PREPARING/Occurrence/Origin、保存源组 binding/manifest、双 Receipt、原 attempt/token；不能把 W5c8g 只读结果当授权。过期 claimed 另门。

本波先解决**源组 hash 是否能在数据库内以与 Python `_digest` 完全同义的方式重算**这一必要门禁。`a0v_045` 存储 JSONB 与 hash，Locator 用 Python `json.dumps(ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)`；直用 `jsonb::text` 摘要有字节差异风险。无此等价证明，不写能 ACK 的半安全函数，也不接 Worker。

## 文件级施工清单

- 审查 `services/aos-api/aos_api/ec_ingress_journal.py::_digest`、`pipeline_snapshot_group_locator.py`、`alembic/versions/a0v_045_snapshot_group_journal.py`，记录空格、键序、Unicode、数值与 JSONB 归一化差异及现有不可变/并发约束。
- 先新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8j_canonical_group_hash_pg.py`，在专用 `aos-a0v-test-only` PG 比较 Python `_digest` 与可候选 SQL 表达式，覆盖真实 binding/manifest 形态及嵌套对象、Unicode、负数/小数、键序。先获得 RED/差异证据；不得通过缩小数据域到单样本来宣称等价。
- 若 SQL 可严谨等价且性能/大小上界成立，再设计单独只读 canonical SQL helper 和隔离负例；若不可等价，本波以 STOP 证据明确安全替代（如保存 canonical byte digest 的新不可变列、历史数据迁移校验/回填）并转下一波。**本波不创建 ACK SQL 函数、不授新 EXECUTE、不在真实库迁移**。
- 同时只读审查 Host guard 与 Delivery 的锁序/事务 API，给下一波列出精确施工文件和拒绝矩阵。浏览器只读检查真实 gate；目录不可用则照实登记。

## 九步与停止条件

1. 复习上位产品/技术恢复约束、W5c8h/i、上述原实现与 authority/Git。
2. 先提交本文件，固定专用 PG/零真实 effect 边界。
3. 在隔离 PG 写 canonical hash 对照 RED 与最小样本集合。
4. 仅对经证明的候选写最小 helper；出现无法严谨等价即停止本波编码并写替代设计。
5. 专项测试、相关短累计，确认测试数据库清理到 0；不复用真实库。
6. 浏览器只读验收（若目录仍不可用则标不可验收），不点业务动作。
7. 方案/代码一致性复审，尤其 JSONB 字节语义、事务锁序、旧入口撤权在真实库未生效。
8. verification 落盘并提交，更新 D-waves、AOS CAS、Prime 回读。
9. 自动下一波：等价证明成功则 W5c8k 设计并隔离实现同事务完整授权；失败则 W5c8k 先解 canonical 保存/迁移门；无完整正负证明绝不接真实 Worker。

真实 closure 保持 `automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`。不读商城源、不重发未知 attempt、不手工 `run_definition`；230 L0 挂起，dev-org 仅零 canary；m1 单写不 push、不动其他分支。
