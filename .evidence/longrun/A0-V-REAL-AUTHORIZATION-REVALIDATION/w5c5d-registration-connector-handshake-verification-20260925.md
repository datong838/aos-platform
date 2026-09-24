# W5c5d registration connector 只读握手核验（2026-09-25）

上位 231 A0-V/231-9 BG-00；方案 `3c825dec` 先行，实现 `eaf56dbb`。本波不调用正式关闭 Owner，不更改凭据/角色/业务库。

## 九步证据

1. 复习原 `registration_connection` 的 0600、非特权独立登录、精确双成员、零 admin option 合同，以及 W3/W4 历史固定配置路径。
2. 文件仅本方案、新增 `scripts/a0v_w5c5d_registration_handshake.py` / `services/aos-api/tests/extension_runtime/test_a0v_w5c5d_registration_handshake.py`、本 verification；Owner/迁移零改。
3. 原受管 connector 内部校验身份后，外层只读事务核 `aos_meta_head`、session/current user 精确注册角色；在 `aos_runtime` 作用域下只读精确 rev4 disabled/hash、原 group 1、closure Receipt 0。无 DSN/密码/凭据正文输出，无商城源行读取。
4. 真实输出 `REGISTRATION_CONNECTOR_READ_ONLY_HANDSHAKE_GREEN`、`automaticAction=false`、`topologyComplete=false`、`closureAuthorized=false`。专项 **4 passed**，覆盖错误角色/数据库/组/Receipt/定义及实现无关闭调用/数据库写入。
5. 有界累计 W5c3–W5c5d、定义、attempt、lease、preparation **204 passed，7 warnings，29.47s**；隔离测试库已停止，更宽慢集此前中止不算 GREEN。
6. 5174 浏览器只读见 12 单路计划与整组入口，`BROWSER_PARTIAL`；无保存、运行、队列冲刷，临时页/前端已关闭。
7. 此 GREEN 仅证明采样时的受管连接、身份和目标库可读，不证明执行时仍可用、全机第二 Host=0 或严格 24h；真实组仍未正式关闭，W5c5b 的时间门及 W5c5c 的不完整拓扑保持。任何未知结果冻结。
8. 本 verification 提交后 CAS 同步 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5e：准备真实关闭/独立审计待执行清单，或继续其他安全研发债；到严格 24h 后才新鲜全门禁、唯一原 Owner 动作与退休。

m1 单写不 push；商城源行不读；旧 attempt 不补跑；dev-org 零 canary；230 L0 挂起，A0-V/BG-00 未过。
