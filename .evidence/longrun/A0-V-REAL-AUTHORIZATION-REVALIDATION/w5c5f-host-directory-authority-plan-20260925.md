# W5c5f 真实关闭前 Host 目录权威只读门方案（2026-09-25）

上位 231 A0-V/231-9 BG-00；W5c5b/c/d/e 明确只读、未关闭，现有本机进程和 connector 观测不能覆盖全机。`ar1_003` 的 Host identity/assignment 是数据库受管权威，不是 OS 进程存活证明。本波只补其精确映射与租约相关状态的只读审计，绝不将目录 GREEN 误作全机拓扑完成。

## 文件级九步

1. 复习 `ar1_003` identity/assignment/历史/Receipt 合同、生产 Host selector、W5c5c 已知 launcher 边界、`a0v_091` 原组关闭门。
2. 文件清单：本方案；新增 `scripts/a0v_w5c5f_host_directory_authority.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c5f_host_directory_authority.py`；本 verification。Host、Owner、迁移均不改。
3. 一次只读一致性快照核 `org-org/dev-project` 唯一 assignment、当前身份及角色 OID、目录 revision/历史 head 对齐、原失败代际的现存资源租约状态计数、原定义/12 Run/Receipt 0。`extension_runtime_execution_attempt` 不持有资源租约的 operation_id 外键，故本波只作精确 generation 范围审计，不声称 operation 级绑定。仅返回必要计数与枚举，不读取商城源行、不读取凭据、不尝试抢锁或启动 Host。任何缺字段/多行/漂移冻结；即使通过也输出 `topologyComplete=false`、`closureAuthorized=false`。
4. 专项覆盖精确目录、rev/OID/历史漂移、额外租约、原组状态漂移与不完整快照；绝不把测试夹具当真实权限。
5. 有界累计 W5c3–W5c5f 与相关合同；隔离库若启动则停用。
6. 浏览器只读核整组 A0-V disabled；页面不证明全机/目录/DB Run。
7. 一致性与风险：DB 目录只能识别受管 Host 分配，无法排除非受管进程/其他物理机或未来竞态。真实关闭需严格 24h、新方案/唯一 key、同事务 Owner 权威门与独立审计；不因本波改写 A0-V/BG-00 状态。
8. verification 落盘提交，再 CAS 更新 docs/AOS 项目开发上下文及 Prime 独立受管记忆并读回。
9. 下一波 W5c5g：结合 W5c5f 真实输出补全全机/权威门，或推进其他不依赖真实关闭的安全债；到线后另立真实关闭方案。

m1 单写不 push；旧 attempt 不重发；230 L0 挂起；dev-org 零 canary；未知冻结。
