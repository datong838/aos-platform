# s3o-w-y 第一切片｜BI 私有进程启动准入

## 复习的上位约束和现场

- 231-3 要求目录/runtime/Web 实际 DB 身份分离，231-9 要求增长包经窄端口和真实 AgentInstance、首链须真商品/客群/场景而非页面 200。E17 D-wave/622 明确 BI issuer 不得借普通 API/owner/runtime、测试口令或默认 HTTP。
- 已有 `aip_network_issuer_process.py`、`aip_private_listener.py` 与 `aip_network_issuer_ipc.py` 提供经验证的不同 UID/内核 peer、路径、有限帧门；s3o-w-v/w-w/w-x 提供至多一次编排、BI 专用 DB 连接、私有线协议。当前本机 `sudo -n -l` 需密码，不能产生真实跨 UID 正向证据；当前 DB 无正式 BI issuer 登录/ACL/IdP，必须失败封闭。

## 文件级方案

1. `services/aos-api/tests/aip/test_aip_bi_plan_issuer_process.py` RED：拒相同 UID、非当前 issuer UID/GID、错 scope、无限连接/等待、相对路径；无外部 OIDC、无 0700 attempt、无独立 BI DB 连接时不创建 socket。一个实例的负例不升级为 Goal blocker。
2. `services/aos-api/aos_api/aip_bi_plan_issuer_process.py`：BI 专用不可变配置，只接受 `BIIssuerDatabaseConfig` 与精确 TenantScope；启动前复核外部 OIDC、私有 attempt 目录、BI 只读 DB 身份；然后复用 `owned_private_listener` 和 `open_private_issuer_listener` 创建有限 Unix listener。对外只提供受检 listener，不接受任意 handler，也不启用 HTTP/Host。后续有限 accept 循环必须先完成原服务/Reader 专用工厂组合，防止 mock/owner 默认连接误入生产。
3. 运行专项与相邻 process/IPC/DB 回归；代码、方案、风险复审；verification、m1 精确提交、D-wave/623/Authority/Prime。

## 退出与下一门

若无正式独立 DB/OIDC 或 UID，启动前应拒绝且无 socket。此波不声称真实跨 UID 或业务正向。下一波先以独立 DB 工厂和原 signed resolver/Plan 服务/Receipt Reader 完整组合有限 accept，并在可销毁全 schema 正向和真实不同 UID 运行门验收；当前库迁移仍要求新备份、恢复演练和零执行窗口。
