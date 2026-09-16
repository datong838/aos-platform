# SC4-5L6Z-Q｜来源游标所有权修复与干净继任窗口方案

日期：2026-09-17。基线：`0080078161c3e5e0b1af18bf479e701168c59076`。本方案属于 231/BG-02 的 A0-V 真实链恢复切片；不增加平行进度分母，不授予外部副作用或 230 L0 权限。

## 1. 当前事实与根因

- 栖月汇 `sch-p02-qyh-controlled-20260913-v1` 已由 Cron 产生真实成功运行 `scr-4eda5462575a4740`，写入 65 行并正常停止；运行表与 ingress journal 均保留该事实。
- `meta_schedule.last_run` 随后退回旧手工运行 `scr-bddff0a74c2a4365`。时间线显示成功运行之后的停用 PATCH 覆盖了游标。
- Scheduler 在同一事务内更新 `meta_schedule_run` 与 `meta_schedule.last_run`；该路径正确。HTTP 计划控制面长期缓存整条 schedule，PATCH 只改 `enabled`，却调用通用全量 upsert，把缓存中的旧 `lastRun` 回写。
- 仅在 PATCH 前强制刷新不能关闭“刷新后、提交前”出现新运行结果的竞态。必须在数据库语句中分离字段所有权。

## 2. 最小技术变更

1. `services/aos-api/aos_api/data_os_store.py`
   - 新增窄的 `persist_schedule_configuration`。
   - INSERT 仍可建立完整计划；ON CONFLICT 只更新 `cron/pipeline_id/enabled/name/ingest`，明确保留当前表内 `last_run`。
   - 用 `RETURNING last_run` 回读执行器权威游标，供控制面刷新缓存。
2. `services/aos-api/aos_api/routers/wave_ext.py`
   - PATCH 改用配置专用持久化入口；持久成功后将返回的权威 `lastRun` 发布到缓存。
   - POST 创建仍使用既有 `persist_schedule`，允许新计划初始化 `lastRun=None`。
   - 未确认写仍清除 scope hydrate 标记并 fail closed；租户校验不变。
3. `services/aos-api/tests/test_schedule_configuration_persistence.py`
   - 调整 PATCH mock 到新入口。
   - 新增回归：缓存旧游标时修改 enabled/name，持久层返回新游标，响应和缓存必须采用新游标。
4. 新增持久层语句测试，证明冲突更新不把旧游标写回，同时跨租户键仍隔离。
5. 主库历史游标已确认被旧 PATCH 永久覆盖，因此新增 `a0v_077` 窄修复权威：只在计划已停用、无运行中任务、当前游标精确等于声明旧运行、目标为同计划最新已停止成功运行时更新；同事务写不可变 Receipt。该函数不是通用游标写口，也不启动计划或来源读取。

## 3. 真实修复与 Q 继任约束

- 代码通过后先重载服务。现存旧游标不直接 DML 修补：使用一次受控、可回读的计划配置 PATCH，使专用语句从当前表保留并返回数据库现值；若数据库现值已经旧化，则从不可变成功运行恢复需要单独迁移/Receipt，不能由缓存猜测。
- P 已正式卸载；Q 必须是新 installation/generation/epoch，经过安装、配置、注册、启用和 exact dispatch 生命周期，不复用 P 权限。
- Q 自然窗口只允许栖月汇真实只读商品源，一次有界 source call；不得修改商城源库制造变化，不得手接 Occurrence/Case/Run。
- 成功标准：计划运行、`last_run`、ingress、ProductEvent、Occurrence、Case/Run 的同源引用可对账；重复副作用 0、`dev-org/dev-project` canary 0。缺少真实变化时保留“无新事件”的合法结果并等待下一自然窗。

## 4. 退出条件

- 单元/持久层专项、受影响 scheduler 测试与 AR2 closure verifier 全绿。
- 主服务代码已重载，修复前后游标和配置变更证据落盘。
- Q 的全生命周期及首个自然窗口证据单独落盘；本切片不能用 fixture、手工建 Case 或旧 P 运行关闭。
- 任一写结果未知、主库版本漂移、租户/代次不匹配或出现非零外部副作用时立即停止该写路径，先读回，不自动重发。

## 5. 计划文件清单

| 文件 | 动作 | 当前 preHash / 边界 |
|---|---|---|
| `services/aos-api/aos_api/data_os_store.py` | 最小修改 | `f8c1701fadb96af2efb778db73db0a14c5fa5a72`；Host 持久化，配置字段不可拥有运行游标 |
| `services/aos-api/aos_api/routers/wave_ext.py` | 最小修改 | `2bb8d9bc758a95d7255b158d24e88f31b62a7cfc`；Host API，只发布已确认结果 |
| `services/aos-api/tests/test_schedule_configuration_persistence.py` | 修改 | `d76590cec6126297e96a93315119b04a85addaac` |
| `services/aos-api/tests/test_schedule_configuration_cursor_pg.py` | 新增 | PostgreSQL 并发/租户所有权专项 |
| `services/aos-api/alembic/versions/a0v_077_schedule_cursor_repair.py` | 新增 | 精确历史游标修复与不可变 Receipt；不授予调度/来源执行 |
| `services/aos-api/tests/extension_runtime/test_schedule_cursor_repair_pg.py` | 新增 | CAS、最新成功目标、运行中/跨租户/幂等反例 |
| `scripts/a0v_z_q_source_cursor_repair.py` | 新增 | m1 单次迁移、修复、读回和证据落盘 |
| `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6z-q-source-cursor-*` | 新增 | 方案、验证及真实运行证据 |
