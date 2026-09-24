# W5c5c Host/维护者身份只读拓扑证据方案（2026-09-25）

上位 231 A0-V/231-9 BG-00；W5c5b 显式 `topologyComplete=false`。真实组仍未到严格 24h。本波只补可复核的拓扑/角色观测，不扩大为关闭授权。

## 文件级九步

1. 复习 `a0v_ecommerce_runtime_host.py` 固定启动器与 singleton 锁、W5c5b、正式 `a0v_091` 的 session_user/role/serializable/admin 门。
2. 文件清单：本方案；新增 `scripts/a0v_w5c5c_host_role_topology.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c5c_host_role_topology.py`；本 verification。生产 Host/Owner/迁移零改。
3. 只读读取本机进程命令行，按 Python 解释器执行的**精确**仓库 Host 脚本参数计数（排除 shell/搜索自身）；读取既有 18181 监听 PID 与固定历史 Host PID 状态；只读查 DB 维护者角色定义/成员关系和 actor admin。不得读取凭据正文、触碰锁、重启/启动进程或查询商城源行。
4. 专项覆盖 0/1/2 精确 Host、shell 文本误报、进程信息缺失冻结、维护者 superuser/bypassrls/成员漂移冻结；任何不完整拓扑返回 INCOMPLETE，不能 GREEN。
5. 有界累计 W5c3–W5c5c 与相关合同测试，隔离库若用则停用。
6. 浏览器只读计划/整组入口，不点保存/运行/队列。
7. 一致性复审：精确脚本计数只能排除**已知启动器**，不能排除其他二进制/主机；需在真实执行方案用 DB 权威租约、全机进程和独立审计做最后门禁。W5c5b 仍 `topologyComplete=false`。
8. verification 提交后 CAS 同步 docs/AOS 项目开发上下文与 Prime 独立受管记忆、读回。
9. 下一波 W5c5d：继续关闭执行方案草案/安全研发债；到严格 24h 后独立实时全门禁、唯一原 Owner 动作、独立 DB 审计、正式退休。

m1 单写不 push；不读商城源行；旧 attempt 不补跑；dev-org 零 canary；230 L0 挂起，未知结果冻结。
