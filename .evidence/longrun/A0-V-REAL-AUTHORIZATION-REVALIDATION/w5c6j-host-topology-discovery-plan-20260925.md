# W5c6j 全机 Host 拓扑只读发现方案（2026-09-25）

上位 W5c5c/f：本机已知 launcher `ps` 为 0、受管 Host directory assignment/identity/3 条旧租约证据 GREEN，但明确不能排除其他 launcher、其他机器、数据库后续竞态。W5c5g 正式关闭门仍 `FULL_MACHINE_HOST_TOPOLOGY` 未解，不能凭单机/DB 单快照把 topologyComplete 改 true。

## 文件级九步

1. 复习 `ar1_003` 受管 Host directory、W5c5c/f/g、真实 closure 门及本机 known launcher/DB active session 的可观测范围。
2. 本方案先提交。只新增 `scripts/a0v_w5c6j_host_topology_discovery.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c6j_host_topology_discovery.py` 和 verification；不改 Host/worker/DB/closure。
3. 只读收集本机 exact launcher PID、受管 directory 快照结论、数据库 `pg_stat_activity` 里目标 DB 的受限 runtime/registration 会话计数与 client_addr 摘要；不打印 SQL/凭据/原始进程 argv，不访问商城源行。
4. 分类永远 `topologyComplete=false`、`closureAuthorized=false`、`automaticAction=false`；任何未知/异常冻结。本机进程或 DB 会话是阻断信号，0 只表示未观察到，不能证明跨机器 Host 静默。外部机器清单/Host 分布授权仍需正式证据机制。
5. 专项合成输入和真实只读观察；W5c5k–z/W5c6a–j 累计回归；旧 skips/timeout 如实列。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审发现器不扩大授权；实时关闭门只读，严格 24h 未到，不调用 closure。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6k：对跨机器 Host inventory 的权威来源/心跳 TTL/身份历史做架构方案与无效应合同；若无法排除非受管 Host，保持 no-effect 并等待严格 24h 后重新审计。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
