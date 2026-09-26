# W5car｜内容持久命令正式执行组合核验

## 现场、上位与范围

方案：同目录 `w5car-content-executor-current-authority-plan-20260926.md`；上位 231 A1、231-5/6、栖月汇双侧增长产品方案、W5caq verification。基线 m1 `6e6d86b7`。本波只接已有内容 Budget Owner、Journal、Worker、exact Provider invoker、Consumer 的正式组合与进程启动门；未启用生产 Worker、未读取商城源数据、未调用真实 Provider、未改变已签名候选包或旧 12 Run。

## 文件级实现与核验

1. `ecommerce_content_execution_journal.py`：租户有界 HELD/v2 PENDING selector 和已记录结果待消费 selector。候选逐项核原命令 hash、预算 Request、原 PENDING Receipt；已 SUBMITTED/UNKNOWN 不会进入新外呼 selector。
2. `ecommerce_content_execution_composition.py`：原当前 Host Dispatch/安装锁与 Plan/Decision/Evidence/预算/容量重验，原 READY exact Route/Price，基于批准方法及来源编号的有界中文 prompt；独立历史 exact Plan 仅供已发生结果记账。runner 先消费旧结果、再执行 HELD、再消费新结果。已知单项权威冲突只挡该项；非预期/未知外呼边界 fail closed。独立状态 Reader 核 ProviderRequest/ProviderResult Receipt、Budget、两种 measured Usage、可读 Artifact hash/正文/TaskRun；`RESULT_RECORDED_UNSETTLED` 不算完成，费用未定为 `COST_PENDING`。
3. `ecommerce_content_execution_worker.py`：原反向锁序改为只读预检→当前 Dispatch/安装锁→预算行锁与再次复核→提交 ProviderRequestReceipt 后 commit→事务外单次外呼；异常标 UNKNOWN 或保持不可重发边界。`aip_exact_provider_invoker.py` 增文字请求实际 `max_tokens` 硬上限，正式组合从不可变命令传递。
4. `main.py`：`AOS_ECOM_CONTENT_WORKER_ENABLED` 默认 false；无同进程 ACTIVE Runtime Host、独立 runtime DB 身份或无效开关值时拒绝启动；启用时由既有进程管理固定 `org-org/dev-project` 的有界循环，任务失败状态可见。没有第二 Host，也没有手工 run_definition。

隔离空 PostgreSQL 127.0.0.1:18432 中，7 个邻接文件累计 **78 passed、7 既有 warnings**（预算、Worker、Invoker、组合、Handoff、进程启动）。`uv run python -m compileall` 与 `git diff --check` 通过。专项测试含跨租户/旧 v1 排除、结果恢复只消费不发送、锁序、输出硬限、默认关闭与 Host 门、状态读回缺 Artifact 拒绝。无 UI/路由改动，浏览器验收 N/A。

## 不能冒充的绿色与遗留风险

旧 `test_a0v_content_result_consumer_pg.py`/`test_a0v_content_usage_pg.py` 在此临时空 PG 的 fixture `LIKE public.aip_lineage_event`/`aip_artifact` 处失败，未进入所测逻辑；`init_schema` 后 Alembic 仍缺 `meta_workspace`。这 9 项**未绿**，需后续经正确公共 schema 基线的隔离 PG 重跑；不能用 78 项邻接绿覆盖。当前 Reader 的完整结算/Artifact 真 PG 端到端也未证明。

生产开关保持关闭；尚无当前真实安装代次、费用/出境、Provider、事实新鲜度与自然 TaskRun 的独立验收。此波不是内容产物或自然业务闭环；UNKNOWN/提交不明绝不自动重发。旧 12 Run 正式退休、230 L0 继续后置；`dev-org/dev-project` 仅零 canary。下波 W5cas：先解决隔离 PG 公共基线并做真实端到端消费回归，再做新签名包版本/安全安装切换和当前 scoped authority canary；只有全门通过才开启一次自然内容执行，接着人工评审续跑。
