# W5c6r 旧 Schedule 单项测试专属阶段计时方案（2026-09-25）

上位 W5c6q：唯一 12 来源 ACK-loss 恢复用例在约 10 分 39 秒仍无终态；setup 15.11 秒，测试库的 12 对象/13 receipt/1 link 已写，12 Run 仍 running。采样栈分别落在 canonical JSON 与 psycopg，不足以归因。必须先定位 `execute` 的 claim、ingress.prepare、completion.complete 哪段耗时，再考虑任何优化。

## 文件级九步

1. 复习 W5c6p/q、`PipelineSnapshotScheduleRuntime.execute` 三段和旧测试 ACK-loss 三次调用。
2. 本方案先提交。只改 `services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py` 测试专属可选计时与 verification；生产/DB schema/部署零改动。
3. 在 `AOS_TEST_SCHEDULE_TIMING=1` 时为 `_claims.claim`、`_ingress.prepare`、`_completion.complete` 加透明 wrapper，仅输出阶段名称/单调秒数；默认不装 wrapper。异常路径也记录 elapsed，不吞异常。
4. 测试先证实 wrapper 不改变调用参数/返回/异常和无标志默认路径；然后单项有界观察最多 360 秒，约 50 秒只读采样。超限中断并标未完成。
5. 运行计时专项、旧其余 16 项与安全累计 111 项；若计时本身显著增负荷，撤回实现并记录。
6. 浏览器只读 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审计时输出不能包含租户数据、凭据或真实源行；只认正式终态，不把阶段完成等同业务完成。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回。
9. 下一波根据最慢阶段做精确根因诊断/最小修复方案；真实 closure 仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
