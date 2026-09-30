# W5CB4 BG00cv｜私有 issuer IPC 与 OS 禁入验证

- 基线：m1 `ecda408b`、AOS-000951；任务 Receipt `W5CB4-BG00CV-20260930`；文件级方案 `w5cb4-bg00cv-private-issuer-ipc-plan-20260930.md`。
- 环境事实：macOS Python `socket.getpeereid` 不存在，libc `getpeereid` 可用；实际 `socketpair(AF_UNIX)` 读取的 peer UID 等于当前 UID。当前 8080 API PID65249、8434 Web PID59876 均由 ddt 运行；`a0v_network_issuer_identity_gate.py --api-pid 65249 --issuer-pid 59876 --credential-file <test-only private pgpass>` 退出2 `ISSUER_OS_IDENTITY_NOT_ISOLATED`。Web 仅作为同 UID 负例，不冒充 issuer。
- RED：新增 IPC 测试首次运行缺模块，8 failed；增加 listener 启动门测试时缺函数，1 failed/10 passed。GREEN：带显式隔离证明目录运行 IPC/service/attempt/auth/reconcile/contracts/network producer 七个文件，退出0，`59 passed, 2 skipped`；compileall 与 `git diff --check` 退出0。
- 实现审查：仅 AF_UNIX stream；macOS 内核 peer UID/GID 必须与可信 API UID 精确一致且 API/issuer 不同非 root；64 KiB 单帧上限、5秒超时、重复 JSON key/未知方法/自报角色与 DB 凭据拒绝。单连接最多一个 inquiry 或 decide_once；返回固定状态/错误 code，不泄 JWT。listener 启动前要求独立 UID/GID、0770 socket 目录、0700 凭据目录和0600 issuer 文件；已有 socket 路径不覆盖、不删除。
- 测试分级：真实同 UID socket 与 OS gate 只能证明拒绝；合成不同 peer 的路由测试只证明协议控制流，不能作为正式跨 UID 或外部 IdP 验收。隔离 clone 只读 Inquiry 由邻接测试覆盖，本波未发正式 Approval Event。
- 未完成：仍无正式独立 issuer 进程/受控 DB 连接工厂、实际跨 UID peer 连接、外部 IdP、当前第二 checker 和当前 HBA 安全切换。BG00cw 须做真实进程启动器、精确 issuer LOGIN/role 连接与故障注入；当前 API/库/Host/worker/Provider 不变，首链仍 pending。
