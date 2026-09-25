# W5c7m `_bound_parent` 子段透明探针 verification（2026-09-25）

## 第 1/9～4/9 步：方案、实现与专项

- 上位 231/231-5、W5c7l 审计及当前调用链已复习。文件级方案先提交 `fef5e76c`，测试专属实现 `bcbc0246`；**生产 `aos_api/`、DB、索引、部署均未改**。
- `AOS_TEST_SCHEDULE_TIMING=1` 才安装测试侧 wrapper。用 `ContextVar` 将 envelope `read`、当前/完成 claim 读、running/completed binding 计时限定在 `_bound_parent` 内；原参数、返回、异常与调用顺序透传，`finally` 记录并复位。只输出次数/单调耗时，不输出原 envelope 或商城源数据；非 opt-in 原路径不包裹。
- 新增 5 项合同测试：非 active 不计数；active 计数并原样抛异常；缺 envelope 直接拒绝、不验 schedule；绑定拒绝不重试；running/completed 分支各自精确选择。原 opt-in 透明测试加 5 个零计数子段断言。专项 **6 passed**。

## 第 5/9～7/9 步：回归、只读验收与风险复审

- Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/m、JDBC 与原透明计时累计 **224 passed**。旧 12-source 长例本波未运行；W5c7k 正式 `MONOTONIC_TIMEOUT`/124 仍不计 GREEN。探针已具备下一次有界单次运行时采集真实子段分布的能力，本波无真实分布结论。
- 真实 gate 当波读回：`REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled closure Receipt 0，仍缺全机 Host topology、单事务新鲜 Owner gate、独立真实 closure 方案和唯一 key。
- 浏览器 `/data/schedules` 只读：A0-V Canonical rev4「已配置 · 已停用」，运行状态「数据组已停用」（2026/9/25 16:31:14），当前身份无权启用。未保存、运行或冲刷待同步写操作 1。临时 Vite 与隔离测试 PG 已停。
- 子段是嵌套计时，completed binding 内可再次读 envelope，不能直接相加或把次数当独立业务尝试。wrapper 没有额外 SQL、外部调用、重试或 fail-open；真实安全等价切片仍未证明，不能据探针删校验。
- 商城源行未读、230 L0 继续挂起、dev-org/dev-project 仅零 canary、m1 单写不 push。旧 attempt 不重发、不手工 `run_definition`。

## 第 8/9～9/9 步：交接

本 verification 提交后 CAS 更新 docs/AOS 跨对话上下文及 Prime 独立长记忆，并读回。下一波 **W5c7n**：先方案，单次有界隔离 PG 长例采集子段；若再次超时，只记正式 timeout 和有限证据，不重跑/不计 GREEN；然后依据真实分布做同事务等价性证明/对抗测试，仍不改真实 closure。
