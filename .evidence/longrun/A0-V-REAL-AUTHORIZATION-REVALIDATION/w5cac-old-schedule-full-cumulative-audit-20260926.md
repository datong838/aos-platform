# W5cac｜旧 Schedule 完整累计与当前风险映射

方案 `m1@4c04ca3d`，收集数订正 `9e068e73`，风险收口补订 `9da9c4c7`。W5c6p 原三模块为 7+9+1=17，其中 16 项分拆通过、长例未到终态；W5c7n 长例单次 1 passed/794.823 秒。当前同三文件 collect 为 **8+9+1=18**，不可沿用旧 17 分母。

2026-09-26 单次专用 `colima-aos-a0v-test-only:5433` disposable PG 会话，`a0v_w5c7j_monotonic_test_runner.py` 限 1500 秒/5 秒宽限：pytest `18 passed, 7 warnings in 487.31s`，runner `CHILD_EXITED`、`childExitCode=0`、`runnerExitCode=0`、`timedOut=false`、`monotonicSeconds=496.166`。测试 `aos_test_*` DB 余量 0；18181 原 PID36529 文档 HTTP200，8080 无监听。无生产/测试代码、真库、真实 Worker/商城源动作。

当前 AOS-000726 `incomplete` 旧索引 17、25–28、30–31 关于“完整组超时/无终态/未绿”的现状已被 W5c7n+本波正式结果覆盖，移出**当前风险**，保留历史证据。索引 18/19 的生产下游 effect 风险仍真，删去旧 timeout/skip 附句并写成真库未迁/未生产围栏；索引 29 的“长例未终态”已假，但 W5c7s 的同一 `_load` claim 复用等价性仍未证，改写为此安全债。索引 7 的非空业务效果未测仍真，但严格 24h 已在 W5ca4 过线，改写时间描述。其余 original Run/Fleet/Store/行证明/真实到期硬门不变。

18/18 GREEN 仅是本版本**隔离测试累计**，不证明业务 Handler/真实 Store/原组 closure，也不授权把重复 claim 权威验证优化掉。历史 W5c7k timeout 不改写为当时成功。
