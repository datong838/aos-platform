# W5c5j Runtime Host 租约 opt-in 与失权停机方案（2026-09-25）

上位 W5c5h 排他设计、W5c5i `a0v_093` 隔离 PG GREEN、AR1-c Host selector。真实 DB 仍 `a0v_092` 且无新表；本波只加**默认关闭**的 Host opt-in，绝不启用或重启真实 Host。

## 文件级九步

1. 复习 `a0v_ecommerce_runtime_host.py` 现有 singleton/worker 生命周期、`runtime_directory_connection` 的强制只读语义、`a0v_093` DB 权限和当前 Host 测试。
2. 文件清单：本方案；新增 `services/aos-api/aos_api/extension_runtime/host_lease.py` 与专项测试；仅 additive 增加 `runtime_connections.py` 的受限租约连接、启动器 `--host-lease-opt-in` 显式参数/生命周期测试；本 verification。Owner/迁移/业务 worker 逻辑不改。
3. 默认不传 flag 完全保留旧路径。显式 opt-in 时，在任何 worker serve/ACTIVE 状态输出前用独立 directory 身份可写连接、租户作用域和 DB 函数申请短 TTL；定期续租，失权/异常触发 Host 停止，待 worker drain 后尝试原 token/epoch release。token 只在进程内存，不写 status/log/env；未知结果不得重试 acquire 或启动 worker。
4. 专项覆盖默认旧行为、opt-in acquire 失败不启动、续租失败停止、正常释放及连接角色/密钥隔离；隔离 PG 覆盖实际函数。
5. 有界 W5c3–W5c5j+Host 合同累计回归，隔离库停用。
6. 浏览器只读核 A0-V rev4 停用；新 flag 默认 off 不改变页面。
7. 风险边界：这只让**显式 opt-in 的一个 Host**持有 DB 租约；旧 Host 与所有 worker 尚未同事务 fencing，故不能当作全机 0、旧代关闭权或 A0-V GREEN。真实库未迁移时 opt-in 必须 fail closed。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆、读回。
9. 下一波 W5c5k：逐 worker 设计/实现同事务 epoch fencing 与隔离故障注入，不在未全覆盖前启用真实 Host。

m1 单写不 push；商城源行不读；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary。
