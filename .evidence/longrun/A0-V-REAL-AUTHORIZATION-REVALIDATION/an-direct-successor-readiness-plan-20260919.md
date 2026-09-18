# AN direct successor 运行前代码闭包方案

## 目标与边界

AM 已正式退休，AN 尚未创建。先关闭真实 saved-input successor 曾暴露但尚未提交的 admission 与 Store 锁边界，保证后继只能复用冻结输入和原幂等 Receipt，不通过创建 AN 来试错。

本波不创建 installation/generation，不注册 successor，不 cutover，不启用 definition，不调用 `run_definition`，不读取商城源，不重发未知 Store 结果。`org-org/dev-project` 是唯一正向 scope，`dev-org/dev-project` 只做零副作用 canary。

## 文件级清单

1. `services/aos-api/aos_api/pipeline_source_claim_owner.py`
   - `read_saved_current` 必须使用同一次 recovery Authority 的 `run_current` 结论区分普通 renewal 和 direct successor。
   - 普通 renewal 仍要求同 control family、revision 单调递增、installation/generation 不变。
   - 跨 family 只在整组 Authority 已验证 successor transfer 时允许；从原 claim ref 解析原 control identity，核对原 ref、actor、installation、generation、pipeline 与完整读取语义。
   - 允许变化仅限窗口、source selection 及 successor installation/generation/execution epoch/configuration/package；run、pipeline、actor、call ordinal、最大源调用次数不放宽。
2. `services/aos-api/aos_api/ec_ingress_recovery.py`
   - 元数据锁事务必须在进入独立 Store 前提交；base/derived replay 始终使用原 command 与原 key。
   - 每次 derived Store 提交前后重开短事务，重新锁定 Run 并比较 parent/saved command；漂移时停止，不删除已存在 Receipt，不重发新 key。
3. `scripts/a0v_snapshot_product_api.py`
   - 启动状态 hash 纳入 group completion 与 recoverable Store attempt 运行代码，便于重载后判断实际加载基线。
4. `services/aos-api/tests/test_ec_ingress_recovery.py`、`services/aos-api/tests/extension_runtime/test_pipeline_source_claim_owner_pg.py` 及相邻 recovery PG 套件
   - 覆盖同 family renewal、合法 successor、伪造 admission、原 ref 查询、身份/语义漂移、Store 前后 current recheck、部分已提交 replay 与零新 source call。
5. `services/aos-api/tests/test_snapshot_product_api.py`、`services/aos-api/tests/test_snapshot_schedule_worker_lifecycle.py`
   - 固定实际加载 hash 与 a0v089 静态 reason 映射；动态异常正文不得进入持久状态。

## 验证顺序

1. 用 `PYTHONPATH=services/aos-api:scripts` 运行纯函数与生命周期专项，区分环境错误和产品错误。
2. 在隔离 PostgreSQL 18434 运行 SourceClaim 与 saved-recovery 组合测试；测试自行清理其 schema，不访问真实商城。
3. 运行 recoverable Store、Worker、group completion、API profile 累计回归，执行 `git diff --check`。
4. 复审方案/代码一致性并提交代码与证据。重载 API/Worker 之前仍要求 running attempt=0；重载只证明代码已加载。

## AN 写阶段门禁

只有本波代码闭包提交、服务重载和只读空窗全部通过后，才从 AM exact detach Receipt 制作 AN replacement 文件；每个写阶段继续使用正式 Owner、CAS 与不可变 intent/result。任何 Receipt unknown、并行 owner、租户串扰或 current-authority 漂移都停止写阶段，只读对账。
