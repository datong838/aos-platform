# W5c7d Fleet 签名资产来源审计核验（2026-09-25）

## 九步结果

1. 已复习 W5c7b/c、Host/closure 上位边界与现有发布物签名、部署和资产来源。
2. 方案先行：`60e420ea`；文件级范围只有审计证据与本核验。
3. 只读来源审计：`53b43281`。Registry Ed25519 是发布物身份而非全机 Host 清单；Apollo fleet 是产品/mock；本机 launchd、Spoke Helm、目录、租约和 DB session 均不覆盖全部可启动机器与入口。没有找到可信的 live fleet 签名控制面来源。
4. 最小后续切片已界定：专用 fleet trust-root namespace 与 domain-separated 信封只能证明签名身份；覆盖性和禁止旧入口重启须由独立控制面及逐节点读回证明。本波未改代码、生产、DB 或部署。
5. 专项审计复核完成；Host/closure + W5c7c 结构分类器 + W5c5k–z/W5c6a–z/JDBC 累计回归 **150 passed**。真实 closure gate 仍为 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`automaticAction=false`、`closureAuthorized=false`、原 Run running=12、stalled closure Receipt=0。
6. 2026-09-25 14:11 CST 浏览器只读验收：A0-V Canonical 为“已配置 · 已停用 · 版本 4”，运行状态“数据组已停用”，当前身份无权启用。未保存、未运行、未冲刷待同步写操作；临时 Vite 与测试 PG 均已停止。
7. 方案/代码一致性：仅审计当前来源；不将包签名、结构分类或局部 Host 计数提升为正式授权。真实库仍 `a0v_092`，lease 未部署且 Host opt-in 关闭，worker 全路径 fence 未证明；不重发旧 attempt，不读商城源行，230 L0 挂起，dev-org 仅零 canary。
8. 本文件提交后按 AOS-000639→640 CAS 更新 docs/AOS 跨对话上下文、Prime 独立长记忆投影并读回；docs 提交另记。
9. 下一波 W5c7e：先方案，再隔离设计/实现专用签名信封及负例；其结果始终 no-authority，不接真实 Host/closure。

m1 单写，不 push；本波没有真实业务效应。
