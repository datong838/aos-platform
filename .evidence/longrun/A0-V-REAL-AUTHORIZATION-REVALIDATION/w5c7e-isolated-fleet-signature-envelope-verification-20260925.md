# W5c7e 隔离 Fleet 签名信封核验（2026-09-25）

## 九步结果

1. 复习 W5c7b/c/d 及 231/231-9 上位边界：Registry 发布物签名不得改名为 Runtime Host 全机权威。
2. 文件级方案先行 `0ba08b23`；仅增加纯验证模块、专项测试和本核验。
3. 最小代码 `8ee9813f`：显式注入 `aos.fleet-trust-roots/v1` 独立 namespace，精确信封、域分隔 canonical JSON、Ed25519 与 W5c7c 结构/时窗、revision floor。无文件/网络/DB/Host/closure 接线；验证成功仍 `automaticAction=false`、`topologyComplete=false`、`closureAuthorized=false`。
4. 专项 20 passed，覆盖有效 isolated key、篡改、错 key/namespace、过期、非 canonical 签名、自报授权与回退/重放。首次样本中将签名末尾 `=` 改为同一字符导致 1 个负例不成立，已改成追加 `=` 并重跑全绿；最初 PG fixture 未启动的 setup 错误也已通过启动隔离 PG 解决。无真实私钥落盘。
5. Host/closure + W5c7c/e + W5c5k–z/W5c6a–z/JDBC 累计 **170 passed**；真实 gate 仍为 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`automaticAction=false`、`closureAuthorized=false`、原 Run running=12、stalled closure Receipt=0。旧 Schedule 长测未重发。
6. 2026-09-25 14:20 CST 浏览器只读：A0-V Canonical “已配置 · 已停用 · 版本 4”，运行状态“数据组已停用”。页面有 1 条待同步写操作，未保存/运行/冲刷；临时 Vite 与测试 PG 已停止。
7. 一致性与风险：签名只能证明注入公钥对应私钥签过精确 bytes；不能证明 trust root 正式生命周期、全机资产覆盖、旧入口禁重启或物理第二 Host=0。真实库仍 `a0v_092`，全 worker fence/Fresh Owner 门未齐。无生产、DB、部署或真实业务效应。
8. 本文件提交后 CAS 更新 docs/AOS 跨对话上下文和 Prime 独立长记忆，读回；docs 提交另记。
9. 下一波 W5c7f：先方案，做专用 trust-root 轮换/撤销/防回退隔离合同与正式控制面来源缺口；保持 no-authority。

不重发旧 attempt、不手工 `run_definition`；不读商城源行；230 L0 挂起；dev-org 仅零 canary；m1 单写不 push。
