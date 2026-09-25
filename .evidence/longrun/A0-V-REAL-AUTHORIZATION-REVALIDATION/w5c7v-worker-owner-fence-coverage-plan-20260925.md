# W5c7v Worker/Owner 事务 fence 覆盖矩阵计划（no-effect）

## 上位与文件级清单

承接 W5c7b/t/u：全机控制面仍缺，W5c7u 只提供默认 off 的 Snapshot 工厂 lease 参数，不是生产接线。先逐一审阅 `services/aos-api/aos_api/main.py`、`scripts/a0v_ecommerce_runtime_host.py`、`services/aos-api/aos_api/ecommerce_{product_event,analysis_data_requirement,baseline_assessment}_worker.py`、`services/aos-api/aos_api/pipeline_control_service.py`，再追踪它们调用的 Automation/Outbox/Store 与 HostTransaction 写入。仅新增本波 `w5c7v-worker-owner-fence-coverage-audit-20260925.md` 和 verification；没有可靠的跨事务接入设计前不改生产代码。

## 九步与检验

1. 复习上位方案、m1 HEAD 与 AOS/Prime memory 当前状态。
2. 本文件先提交，明确上述文件及 Owner/Store 边界。
3. 形成逐入口矩阵：启动、lease 传递、同事务 fence、外部效果/未知边界、默认真实状态；不把 `host_ready()` 当事务 fence。
4. 跑现有 opt-in Host lease 和相关 worker 专项；如出现可隔离缺陷再另起红绿最小修复。
5. 跑近期 A0-V 累计回归；不运行旧长例充数。
6. 浏览器只读确认 rev4/组停用，不冲刷待同步队列。
7. 复审矩阵与代码逐项一致，明确未证范围；真实 closure 只读门复验。
8. verification 落盘提交 m1，CAS 更新 docs/Prime 三投影并回读。
9. 自动进入 W5c7w：选择单一可写 Owner（优先 `PipelineControlServices`）做默认 off 的同事务 fence 方案与隔离 Red-Green；三业务 worker 独立路径另列计划，不能一个参数冒充全集。

真实 `a0v_093/094` 不部署、Host 不启 lease、不重发旧 attempt、不手工 `run_definition`，商城源行不读；230 L0 挂起、dev-org 零 canary、m1 单写不 push。
