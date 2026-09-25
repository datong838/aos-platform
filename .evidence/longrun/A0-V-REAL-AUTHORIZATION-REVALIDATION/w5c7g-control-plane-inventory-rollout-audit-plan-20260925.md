# W5c7g 控制面清单与安全 rollout 缺口审计方案（2026-09-25）

上位 W5c7b–f 与 231/231-9：隔离结构、签名和根生命周期只证明输入合同，不提供真实全机清单。真实 DB `a0v_092`、Host opt-in off、12 原 Run running、stalled Receipt 0；任何部署/迁移/closure 均未获授权。

## 文件级九步

1. 复习上位方案、W5c7d 来源审计、Host 启动脚本/launchd、容器/CI/手工入口和控制面接口。
2. 本方案先提交；只新增 `w5c7g-control-plane-inventory-rollout-audit-20260925.md` 与 verification，不改代码、DB、服务配置或部署。
3. 列出“已知可启动面”与“未知/未受管面”的证据来源、当前控制者、是否能禁止旧入口重启和如何逐节点读回。不能用本机 `ps` 或 DB session=0 外推全机。
4. 明确正式 rollout 前置：独立控制面与签名根来源、完整资产/部署交叉清单、旧角色/启动权撤销、每节点 ACK、物理第二 Host=0、worker 事务 fence、真实迁移独立 plan/key/回滚。
5. 跑相关专项/累计回归与只读真实 closure gate；测试 PG 用后停。
6. 浏览器只读 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审审计与代码/部署一致性，不把“建议 rollout”写成已执行。
8. verification 后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7h：先方案，针对审计找到的可执行、无真实效应最小切片继续；若无可信控制面，做隔离 rollout 决策表/拒绝合同，不迁移真实 DB、不执行 closure。

停止条件：未知提交边界或任何真实 Host/业务状态漂移先冻结读回；旧 attempt 不重发、不手工 `run_definition`。商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。
