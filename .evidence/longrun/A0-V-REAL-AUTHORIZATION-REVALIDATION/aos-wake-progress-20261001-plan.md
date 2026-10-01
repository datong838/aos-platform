# AOS 唤醒进展检测与接续强化

用户2026-10-01授权强化唤醒方案。Rules：aos-engineering-delivery、AGENTS、m1单写。基线7cc9c6aa/AOS-001071。现象：aos-2正常送达，但每轮仅重复核对；Goal blocked；旧watchdog错线程且disarmed。不能承诺永不中断。

## 文件与实施
1. 新增scripts/long-task-watchdog/aos_wake_progress.py：读取m1 HEAD、最近services/apps/bundles/scripts代码路径提交；忽略md/txt/png/json/log等文档证据提交。以提醒ISO时间为event id，持久计数与去重。跨线程/仓库/分支异常拒绝；文件锁保护计数，原子写0600。无数据库、网络、进程启动、Goal状态变更。
2. 新增test_aos_wake_progress.py，先RED：重复提醒、旧提醒、无提交计数、新代码重置、30分钟阈值、文档不算代码、线程不符。
3. 更新既有aos-2，保留15分钟及目标线程。命令检测只是导航，不证明业务或写者归属；需核实活跃轮次及Lease，不能把API/Web存活当开发活动。无代码>=2轮或>=30分钟触发实际进展复查，正在运行的测试等须有新证据；停滞转选授权独立任务；实质待裁决不自动批准。没有安全任务时明示阻塞、恢复入口，不空回复。
4. aos每日重启不改；旧watchdog不改绑/启动，避免第二调度写者。Goal恢复须用支持的用户控件；检测器不篡改状态。用户暂停优先。

## 完成判据与风险
测试GREEN、实际检测输出、自动化工具更新及回读一致、精确提交/上下文同步。真正下次定时触发尚需现场验收；检测器由heartbeat调用，不能在Codex/电脑离线时自行运行或通知。没有新代码只是复查信号，不等同无进展；文档-only合法工作需从Receipt/测试/调查结果人工复核。不为刷新时间戳而造提交。回滚用automation工具恢复旧prompt，保留审计state。
