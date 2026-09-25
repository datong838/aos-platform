# W5c6t Link/Object 子阶段测试专属计时方案（2026-09-25）

上位 W5c6s：硬超时单项 `links_execute` 约 241 秒，占 Completion 已观察的大部分；其内先 `_objects.execute` 遍历 12 个 `_single.resume_saved`，再准备/应用/投影 Link。中断前未获正式终态，不能改生产热路径或宣称回归 GREEN。

## 文件级九步

1. 复习 Link/Object/Single 原实现、W5c6r/s 计时、D2.6 与 A0-V no-effect 边界。
2. 本方案先提交。仅改 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 现有 opt-in 探针、加 verification；生产/DB/部署零改。
3. 透明记录 `objects_execute` 总耗时与 12 次 `single_resume_saved` 单次耗时，仅标签/秒数，不打印 run/ref/行；默认无探针，异常原样传播。
4. 外部进程 300 秒硬超时单项；超时 SIGINT，确认一次性测试库清理。若 `_objects.execute` 本身耗尽预算，以 12 个单次计时判断分布，不推断 Link 后半段。
5. 探针合同、旧其余 16 项、安全累计回归；任何超限/skip 不计绿。
6. 浏览器只读 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审计时影响、信息泄露、方案/代码一致性；仅在精确根因定位后制定生产/测试优化方案。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回。
9. 下一波依据 12 次 Single 分布进入最慢子段根因审计或按真实闭环门重新评估；先方案后编码。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
