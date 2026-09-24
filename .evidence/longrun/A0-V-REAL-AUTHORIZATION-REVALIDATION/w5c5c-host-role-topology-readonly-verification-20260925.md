# W5c5c Host/registration 角色只读拓扑核验（2026-09-25）

上位 231 A0-V/231-9 BG-00；方案先行 `c7e655b4`，实现/细化 `dda2698e`。不调用关闭 Owner，不打开凭据正文，不触碰 Host 锁。

## 九步证据

1. 复习固定 Host 启动器与锁、W5c5b、正式 `a0v_091` 的独立维护者身份门。
2. 文件限本方案、新增 `scripts/a0v_w5c5c_host_role_topology.py` / `services/aos-api/tests/extension_runtime/test_a0v_w5c5c_host_role_topology.py`、本 verification；生产 Host/Owner/迁移零改。
3. 只读按 Python argv 的精确脚本参数计已知 Host 启动器，排除 shell/内联文本；只读 pg_roles/pg_auth_members 核正式 registration 登录角色。首次进程采集遇其他进程命令行非 UTF-8，fail closed；改为替换无法解码字符后，真实返回 `knownHostCount=0`、`registrationRole=aos_ecommerce_registration_control`、精确 `{aos_runtime,aos_extension_maintainer}` 成员、非 superuser/非 bypassrls/无 admin option。
4. 专项 **4 passed**：0/1/2 已知 Host、shell 假阳性、角色属性/成员/admin option 与底层预检漂移。普通 A0-V runtime 登录缺 maintainer 成员是预期隔离，正式 Service 用独立 registration 连接；不可把两者混同。
5. 有界累计 W5c3–W5c5c、定义、attempt、lease、preparation **200 passed，7 warnings，29.17s**；隔离库已停止，更宽慢集此前中止不算 GREEN。
6. 5174 浏览器只读见 12 单路计划和整组入口，`BROWSER_PARTIAL`；无保存、运行、冲刷队列，临时页/前端已关闭。
7. 实时输出 `KNOWN_LAUNCHER_QUIET_REGISTRATION_ROLE_READY_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`topologyComplete=false`、`registrationConnectionVerified=false`。精确启动器进程 0 不排除其他 Host 形态/机器；角色元数据不等同受管连接成功。W5c5b 仍 `STALLED_WAIT_24H`，严格最早 `2026-09-25T20:00:04.800482+00:00` 后。真实执行方案必须独立全机/DB 权威核验。
8. 本 verification 提交后 CAS 同步 docs/AOS 项目开发上下文及 Prime 独立受管记忆、读回。
9. 下一波 W5c5d：继续独立受管 connector 握手/拓扑权威的只读方案或其他安全研发债；到线后新方案、唯一原 Owner 动作、独立审计、正式退休。

m1 单写不 push；商城源行不读；旧 attempt 不补跑；dev-org 零 canary；230 L0 挂起，A0-V/BG-00 未过。
