# W5c5d 独立 registration connector 只读握手方案（2026-09-25）

上位 231 A0-V/231-9 BG-00；W5c5c 仅证明注册角色元数据和已知启动器进程 0，`registrationConnectionVerified=false`。真实组仍未到严格 24h。本波仅用正式受管 connector 只读握手，不调用关闭 Owner。

## 文件级九步

1. 复习 `ecommerce_growth_registration_connection.py` 的 0600/独立登录/精确双成员/零 admin option 校验、W3/W4 正式关闭历史所用配置、W5c5c、`a0v_091`。
2. 文件清单：本方案；新增 `scripts/a0v_w5c5d_registration_handshake.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5d_registration_handshake.py`；本 verification。正式 Owner/角色授权/迁移/凭据文件零改。
3. 使用 W4 已证的固定受管配置路径，原 `registration_connection` 内部验证身份；外层只读事务核 `current_database()` 等于当前 AOS 目标、session_user/current_user 精确注册角色、目标定义/组可见及 closure Receipt=0。输出只含状态和非秘密身份，不打印 DSN/路径内容、凭据正文、源行。连接拒绝或目标不一致冻结。
4. 专项模拟错误角色/数据库/Receipt/底层预检冻结、连接异常冻结；确认代码无关闭函数、无写事务。
5. 有界累计 W5c3–W5c5d 及相关合同测试，隔离库若启动则停用。
6. 浏览器只读计划/整组入口，不点击保存、运行或队列。
7. 一致性与风险：握手只证明采样时 connector/角色/库可用，不证明未来执行时仍可用、不解决第二 Host 全拓扑或 24h 门；真实执行仍需新方案与事务内全门禁。
8. verification 提交后 CAS 同步 docs/AOS 项目开发上下文与 Prime 独立受管记忆、读回。
9. 下一波 W5c5e：准备真实关闭的待执行清单/独立审计方案或继续安全研发债；到严格 24h 后才可逐门复核、唯一原 Owner 动作与正式退休。

m1 单写不 push；不读商城源行；旧 attempt 不补跑；dev-org 零 canary；230 L0 挂起，未知结果冻结。
