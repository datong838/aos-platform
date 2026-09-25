# W5c7a 真实 Host Fleet 前置门复核方案（2026-09-25）

上位 231/231-9 BG-00 与 W5c5h、W5c6j/m：本机 launcher、受管目录和已知 DB 会话只能证明局部观测，不能证明全机器 Runtime Host 全集。真实 `aos_meta_head` 尚在 `a0v_092`，未来 lease/fence 代码未成为现场权威；24 小时时钟到线也不自动授权 closure。

## 文件级九步

1. 复习 231-9、W5c5h/W5c6j/m、`a0v_w5c6j_host_topology_discovery.py`、`a0v_w5c5g_real_closure_gate_composition.py` 和当前迁移/Host 状态。
2. 本方案先提交。本波仅增加本 plan、verification；不改生产/测试/DB/部署。执行只读现网拓扑发现、正式 closure 合成门与本机/部署来源对照。
3. 明确区分 live 观测与全机权威：零进程/零会话、目录 release、launchd/Helm 模板、单机 `flock` 均不能消除未受管或离线 Host；若发现漂移立即冻结，不触发 closure。
4. 检查 real migration revision、Host/worker opt-in 状态和当前进程；只读，不启动/停止 Runtime Host，不补跑旧 attempt。
5. 跑 Host topology/closure/lease 相关专项与 W5c5k–W5c6z/JDBC 累计安全回归；测试 PG 用后停。
6. 浏览器只读 rev4 停用；待同步队列不冲刷。
7. 复审：若仍缺全机器 inventory，则记录具体权威来源/接入前提，真实 closure 继续 no-effect；不能用未受管机器“未观测到”作为排他证明。
8. verification 后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立记忆并读回。
9. 下一波 W5c7b：先方案，依据本波来源差距实现/锁定可信 fleet universe 的 fail-closed 合同或迁移接入清单；即使 24 小时到线也先过 Host/Owner 门。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。
