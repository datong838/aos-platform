# W5c7h 隔离 Rollout 拒绝合同方案（2026-09-25）

上位 W5c7b–g、231/231-9：正式 Fleet 控制面、签名根来源与全机覆盖均缺。此波只把已识别的拒绝条件编成离线纯合同，不给任何实库迁移/Host cutover/closure 授权。

## 文件级九步

1. 复习 W5c7g rollout 顺序、W5c7c/e/f 的固定 no-authority 输出及真实 gate。
2. 先提交本方案；新增 `scripts/a0v_w5c7h_rollout_rejection_contract.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c7h_rollout_rejection_contract.py`、verification；无生产接线。
3. 纯分类器接收显式注入的阶段证据，仅允许精确字段/类型；逐项拒绝未证明 signer/root 来源、资产与部署同 revision 覆盖、所有启动面纳管、旧入口禁重启/逐节点 ACK、真实迁移、worker 同事务 fence、物理第二 Host=0 与 Fresh Owner 独立计划/key。即使全部自报 true，也只能返回 `SELF_ASSERTED_READY_NO_AUTHORITY`，三个授权标志恒 false。
4. 专项负例覆盖每一门单独缺失、未知字段/错误类型、局部零进程冒充全机、输入不变；绝不读取文件/网络/DB。
5. 专项及 Host/closure、W5c5k–z/W5c6a–z/JDBC 累计回归；临时 PG 用后停。
6. 浏览器只读 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审合同与上位/代码一致性，说明自报 true 不等于可信控制面或授权。
8. verification 提交后 CAS 更新 docs/AOS 上下文和 Prime 独立长记忆并读回。
9. 下一波 W5c7i：先方案，转向阻碍真实安全性的其它可独立测试债（旧 Schedule 长测或 Store 外部效果），仍不动真实关闭。

旧 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push；未知结果冻结读回。
