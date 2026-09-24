# W5c5j Runtime Host 租约 opt-in 核验（2026-09-25）

上位 W5c5h/W5c5i、方案 `89f4c969` 先行，实现 `7bc88d40`。仅代码与隔离 PG 验证，未重启真实 8080/18181/Host，未迁移真实库或运行旧组。

## 九步证据

1. 复习现有 Host/worker 生命周期、目录连接只读合同、`a0v_093` 的函数/角色/OID/assignment 边界。真实库此前为 `a0v_092`；本波未应用迁移。
2. 文件级改动仅新增 `services/aos-api/aos_api/extension_runtime/host_lease.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c5j_host_lease_opt_in.py`，追加 `runtime_connections.py` 的独立受限可写租约连接和 `scripts/a0v_ecommerce_runtime_host.py` 的显式 `--host-lease-opt-in` 生命周期；业务 worker、Owner、迁移与前端未改。
3. flag 默认 off；显式启用时取得精确租约后才输出 ACTIVE/启动 Host 与 worker。内存 token 单次 acquire，5 秒续租/30 秒 TTL，续租失败触发停机并在 worker drain 后尝试 release；连接使用隔离 directory 身份/角色/租户作用域。真实库未迁移时 acquire fail closed、不启动 worker。不能用该 flag 代替全机拓扑或逐 worker 同事务 fencing。
4. 专项 **5 passed**，含默认 off、未知 acquire 不重试、失败不发布 ACTIVE、续租失权停机/释放、隔离 PG 真实 SQL 函数 acquire→renew→release 与事件读回。初次未启动隔离 PG 得 4 个连接错误，启动后专项通过；未触碰真实库。
5. 累计分组 **317 passed、11 skipped** 加定义合同单独 **24 passed**，合计 **341 passed、11 skipped、7 warnings**。单进程合跑出现旧夹具跨模块清空 `AOS_DATABASE_URL` 造成 16 个顺序相关 setup 错误；拆组后分别全绿，记录为待修测试隔离债，不把合跑红灯伪称绿。隔离 `aos-dev-pg` 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V 整组“已配置 · 已停用 · 版本 4 · 十二类来源”；`BROWSER_PARTIAL`，不证明后端租约已部署。未保存/立即运行/冲刷待同步队列；临时页和 Vite 已关闭。
7. 实时只读门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 个原 Run running、stalled Receipt 0，严格资格线 `2026-09-25T20:00:04.800482Z`。本波仅 opt-in 单 Host 代码；旧 Host/worker 尚无统一租约围栏，真实全机 0 未证，不能赋予关闭权或 A0-V GREEN。前置阶段异常可让未启动 worker 的租约等 TTL 过期；需要后续治理，不会由此产生业务写入。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆、读回；记忆不得把本波当作真实上线。
9. 下一波 W5c5k：逐 worker 设计/实现同事务 epoch fencing 与隔离故障注入，先方案后编码；未全覆盖前不启用真实 Host。

m1 单写不 push；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary；商城源行不读。
