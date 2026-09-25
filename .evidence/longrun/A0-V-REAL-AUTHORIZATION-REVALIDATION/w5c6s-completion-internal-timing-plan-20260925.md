# W5c6s Completion 内部测试专属计时方案（2026-09-25）

上位 W5c6r 已用透明 opt-in 计时确认 claim <0.4 秒、ingress.prepare 约 7/4 秒，而 `completion.complete` 超过 370 秒仍未终态；仍不能判定其内部对象/Link、Retirement、Finish 或 Owner 的具体瓶颈。真实 A0-V rev4 disabled，closure 不授权。

## 文件级九步

1. 复习 `PipelineSnapshotGroupCompletion.complete`、`ControlledSnapshotGroupRetirementExecutor.execute` 的 `_links.execute`、`_finish` 与 W5c6r 测试探针。
2. 本方案先提交。只改 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 测试 opt-in 探针与 verification；生产/DB/部署不改。
3. 在原 `AOS_TEST_SCHEDULE_TIMING=1` 下增 `links_execute`、`retirement_execute`、`completion_finish` 透明 wrapper；合同核参数/返回/异常、默认无探针，输出仅标签与耗时。
4. 单项运行由外部进程硬超时 300 秒强制中断，不再靠手工轮询界限；先只读确认临时数据库命名/资源释放，超时不计通过。
5. 专项合同、旧其余 16 项与安全累计回归；如计时改变语义或产生敏感输出则撤回。
6. 浏览器只读 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审内部阶段与代码一致性、是否有具体修复依据；仍无终态就保留债，不放宽断言。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回。
9. 下一波只针对已定位最慢子段做方案和最小变更，或转其他安全独立债；真实 closure 始终 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
