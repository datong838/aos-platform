# W5c7h 隔离 Rollout 拒绝合同核验（2026-09-25）

## 九步结果

1. 复习 W5c7b–g、231/231-9 与真实 closure gate，确认自报输入不可成为控制面证明。
2. 方案 `f4dfae8b` 先提交，范围仅纯分类器、专项测试和本核验。
3. 代码 `6a74861e` 对精确阶段证据逐项列拒绝原因：签名与根来源、资产/部署全机覆盖、启动面纳管、旧凭据撤销、逐节点 ACK、真实 DB fence 迁移、全部 worker 事务 fence、物理第二 Host=0、Fresh Owner 计划/key。即使全部自报 true 仍 `SELF_ASSERTED_READY_NO_AUTHORITY`，三授权标志 false；无文件/网络/DB/Host/closure 接线。
4. 专项 **20 passed**，含每门单独缺失、多个缺口、非零第二 Host、类型/额外字段、自报授权/局部零进程输入；输入不变。
5. Host/closure + W5c7c/e/f/h + W5c5k–z/W5c6a–z/JDBC 累计 **211 passed**；真实 gate `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、原 Run running=12、stalled closure Receipt=0。
6. 2026-09-25 14:49 CST 浏览器只读：A0-V Canonical “已配置 · 已停用 · 版本 4”，运行状态“数据组已停用”；待同步写操作 1 未冲刷。临时 Vite 与测试 PG 已停。
7. 一致性与风险：分类器是离线拒绝合同，不验证证据来源；全部自报 green 也不等于真实可部署。真实库仍 `a0v_092`，全机控制面/worker fence/Fresh Owner 未齐；未做真实迁移、cutover 或 closure。
8. 本文件提交后 CAS 更新 docs/AOS 上下文和 Prime 独立长记忆并读回；docs 提交另记。
9. 下一波 W5c7i：先方案，处理仍阻碍安全性的旧 Schedule 长测或 Store 外部效果技术债；保持 no-effect。

旧 attempt 不重发、不手工 `run_definition`；商城源行不读；230 L0 挂起；dev-org 零 canary；m1 单写不 push。
