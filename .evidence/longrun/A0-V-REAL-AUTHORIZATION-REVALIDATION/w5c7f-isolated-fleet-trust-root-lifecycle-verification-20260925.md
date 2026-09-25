# W5c7f 隔离 Fleet Trust Root 生命周期核验（2026-09-25）

## 九步结果

1. 复习 W5c7b–e、Registry trust-root 范例及 231/231-9；既有发布物根不复用为 Fleet 根。
2. 方案 `a0ac0571` 先提交；文件级范围是独立纯模块、测试和本核验。
3. 代码 `5d03c7f4` 检查显式注入的 `aos.fleet-root-snapshot/v1` 精确字段、单调 snapshotRevision floor、唯一 keyId、32-byte 公钥、有效区间/撤销时间，再调用 W5c7e 验签。无真实文件/环境/网络/DB/Host/closure 接线。通过仍三授权标志 false。
4. 专项 **21 passed**，覆盖新旧 key 重叠轮换、撤销旧 key、过期/未生效、重复/未知 key、错误 namespace、篡改、snapshot/fleet revision 回退与无效时钟。输入不变，无真实私钥落盘。
5. Host/closure + W5c7c/e/f + W5c5k–z/W5c6a–z/JDBC 累计 **191 passed**；真实 gate 仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、原 Run running=12、stalled closure Receipt=0。
6. 2026-09-25 14:30 CST 浏览器只读：A0-V Canonical “已配置 · 已停用 · 版本 4”，运行状态“数据组已停用”，当前身份无权启用。1 条待同步写操作未冲刷；临时 Vite 与测试 PG 已停止。
7. 一致性与风险：快照来源没有签发/分发/持久防回退权威；模块只能做形状、窗口与注入 key 的验签。全机资产覆盖、旧入口禁重启、物理第二 Host=0、真实 DB `a0v_093/094` 与 Fresh Owner 门均未证明。无真实 effect/closure 授权。
8. 本文件提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回；docs 提交另记。
9. 下一波 W5c7g：先方案，审计真实控制面/部署清单接入缺口与安全 rollout；不得因隔离合同迁移真实 DB 或执行 closure。

旧 attempt 不重发、不手工 `run_definition`；商城源行不读；230 L0 挂起；dev-org 零 canary；m1 单写不 push。
