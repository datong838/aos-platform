# W5c6v Current 重读聚合计时方案（2026-09-25）

上位 W5c6u：Object 逐成员与 Link/Retirement 跨独立 Store 提交后的 current 重读是安全边界，不得凭长时单项直接删减。W5c6t 的 300 秒测试仅显示 Object 约 110 秒、Link 约 199 秒、Retirement 约 264 秒；尚无各 journal 调用次数和总耗时证据。

## 文件级九步

1. 复习 W5c6r–u、Object/Link/Retirement 原实现及 A0-V no-effect、真实闭环门。
2. 本方案先提交。仅修改 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 现有 `AOS_TEST_SCHEDULE_TIMING=1` 测试专属探针，增加该探针合同；另增本波 verification。生产、DB、部署零改。
3. 透明聚合 Object journal `read_current`/`run_current`、Link command journal `read_current`、Retirement journal `read_current` 的调用次数及单调耗时；只输出标签/次数/秒，不输出参数、行、引用或业务内容。默认未启用时零包装；参数、返回、异常原样保留。
4. 在外层 Completion 探针 `finally` 输出一次聚合，即使测试由有界 SIGINT 中断也留证；外部 300 秒硬超时，给清理 20 秒，核实一次性测试库已删。计时不能等同生产性能。
5. 探针专项、旧 Schedule 非长时项、W5c5k–W5c6v/JDBC 累计回归；长时项若仍超限，不计绿。
6. 浏览器只读 rev4 停用和真实 closure no-effect；不保存、不运行、不冲刷待同步队列。
7. 复审探针副作用、时间聚合与原方案一致性；若定位在 journal 方法，下一波再细分 canonical JSON/DB 段，未经等价性证明不改生产。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c6w：依据聚合结果，先方案再做最热 journal 内部测试专属分段；真实门未到 24 小时时继续 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
