# W5c7u Snapshot worker Host lease 传递计划（default-off）

## 上位方案与现状

继承 W5c7b/t 的全机 Host universe 缺口与 W5c5t–z 的逐层事务 fence 合同。`PipelineSnapshotScheduleRuntime` 和 `PipelineSnapshotGroupRecoveryRuntime` 已支持可选 `OptInHostLease`，但 `PipelineControlServiceFactory.build_snapshot_worker` 不接收/传递它，真实 `main.py` 仍构造默认路径。A0-V Runtime Host 另有可选 lease，但并不覆盖此独立 Schedule worker；本波不碰真实 Host/DB。

## 文件级清单与九步

1. 复习 `AGENTS.md`、W5c7b/t 与 `pipeline_control_service.py`、两个 runtime 构造合同、`main.py` 生产入口。
2. 本文件先提交。变更限定 `services/aos-api/aos_api/pipeline_control_service.py` 与 `services/aos-api/tests/test_pipeline_control_service.py`；后续审计/verification 各新增一份 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5c7u-*.md`。
3. 先红测：工厂仅接受 exact `OptInHostLease` 且其 `scope` 与 worker scope 完全一致；向 Schedule 与 Recovery 传同一对象；省略时均为 None。之后做最小参数透传，不修改 `main.py`，不默认启用。
4. 专项覆盖默认路径、有效/错误类型与跨租户拒绝，不需要真实 lease acquire 或外部 Store。
5. 累计 A0-V no-effect 回归和原工厂测试；测试 DB 仅临时库。
6. 浏览器只读确认 A0-V rev4 停用及当前组停用；不点击写操作。
7. 复审两个 runtime 对象相同、所有 downstream fence 既有逻辑不变，生产 `main.py` 仍不注入；不能以此证明全部 worker 覆盖或真实 closure。
8. verification 落盘提交 m1，CAS 更新 AOS 上下文并读回 Prime 三投影。
9. 自动进入 W5c7v：盘点 `main.py` 独立 Schedule worker 与 A0-V Runtime Host 三业务 worker 的启动/事务路径和未覆盖层，不提前部署真实 opt-in。

停止：任何实际 Host、定义、旧 attempt、真实迁移/Store 状态未知均冻结；不重发、不手工 `run_definition`。230 L0 挂起，商城源行不读，dev-org 零 canary，m1 单写不 push。
