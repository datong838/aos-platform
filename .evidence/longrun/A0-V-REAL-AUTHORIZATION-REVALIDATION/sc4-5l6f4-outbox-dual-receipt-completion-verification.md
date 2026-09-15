# SC4-5l6f4 Outbox 双 Receipt 完成权威验证

日期：2026-09-15  
基线：`918943b9`

## 实现与边界

- 新增 `services/aos-api/alembic/versions/a0v_050_data_requirement_outbox_completion.py`，为原 Delivery 行增加成对的 `completion_fulfillment_ref` 与 `completion_analysis_ref`，并提供两个固定 `SECURITY DEFINER` 转换入口。
- 正常 `complete` 只接受当前 `claimed`、同 attempt/token 且未过期 Lease；`reconcile_completed` 只接受当前 `unknown` 和同 attempt/token，允许在提交结果未知后越过 Lease 到期做只读凭据核对。
- 两个入口都由数据库逐项验证原 Outbox/Requirement、完整 fulfilled DataFulfillmentReceipt 权威、RUNNING 且 `completed=false` 的统一 AnalysisRuntimeReceipt、requestHash、Requirement/Fulfillment/Run exact 谱系。Requirement 权威存储保留 `receiptId:null`，传输合同省略该空字段；校验只规范化这个既有可空字段，其余类型、ID、版本和哈希仍完整相等。
- 修改 `services/aos-api/aos_api/data_requirement_outbox_store.py`，新增严格 Claim/exact-ref 适配器；旧 `ack/fail/mark_unknown/reconcile_unknown` 保持兼容。运行角色只获新增函数 EXECUTE，没有 Delivery、Outbox、Fulfillment 或 Host Receipt 直接写权限。
- 本段没有建立 worker、生命周期启动、Provider 调用或外部业务副作用；l6f5 才能组合 claim → route → coordinator → complete。

## Red 与修复证据

1. 有效 Red 首先因 `a0v_050` 文件不存在而失败，记录于 `/tmp/sc4-l6f4-red.log`。
2. 首次真实 PG 完成被双 Receipt 数据库门拒绝。读回发现原 Fulfillment/Requirement/Run 权威 JSON 明确保留可空 `receiptId:null`，而运行传输 exact ref 按既有合同省略空字段；方案与 SQL 同步改为只规范化该字段，没有改成模糊 ID 匹配。
3. 成功确认后的外层 SERIALIZABLE 验证连接仍看见旧 `claimed`，验证改为先结束旧快照再读权威行；没有重试产品写入。
4. Lease 故障注入最初误用 `aos_runtime` 直接 UPDATE，被数据库按设计拒绝。最终仅由每用例私有数据库的管理员连接拨动测试时钟，产品路径和运行角色权限未改变。

## 新鲜验证

- 双路径完整协调与完成：`2 passed / 231.65s`。覆盖正常 complete、unknown reconcile、双 Receipt 留存、相同命令重放、canary 不可见和运行角色直接 UPDATE 拒绝。
- unknown 对称负向补测：`1 passed / 118.30s`。覆盖 reconcile 自身拒绝旧 attempt、错 token、缺失 Fulfillment Receipt 和 PREPARING Analysis Receipt，并证明 Lease 过期后只有 unknown + 原双 Receipt 能恢复。
- 新旧 Outbox Store 与空库升降级：`8 passed / 9.88s`。`a0v_049 → a0v_050 → a0v_049` 可逆，旧 delivery 合同保留。
- 累计相邻回归：`19 passed / 341.27s`，包含上述 8 项、原 route、六策略集合与原生完整快照恢复链。
- 修改 Python 文件 `py_compile` 通过；`git diff --check` 通过。
- `verify_closure.py --phase ar2-7`：`1955 scanned / 195 classified / 93 migrated`，hash、正反依赖、跨层导入和动态引用五类错误均为空。
- Prime/shared-memory：七个强一致投影均为 `CURRENT`，Codex eventual 投影仍为 `PENDING_ASYNC`；`memoryctl validate` 为 `GREEN`，AOS-000573，1201 Delivery / 1183 Task / 2900 Event。

专项使用每用例私有全迁移 PostgreSQL、named 商城读取和 named 安装发布资产。它证明 Outbox 完成权威、幂等、租户隔离和故障恢复边界，不代表主库已升级、真实栖月汇事件已由常驻 worker 消费、真实模型分析或八工作台经营场景已经完成。

## 下一项

SC4-5l6f5 实现固定 DataRequirement Outbox worker：从生命周期拥有的明确依赖构造 ProductEventAnalysisService、读取当前 Claim route、调用固定 snapshot coordinator，并只用本段双 Receipt 完成接口确认；处理进程异常、提交结果未知、Lease 过期、停止/重启和无任务空轮询。随后接入应用生命周期，证明无需开发者手工调用协调器。
