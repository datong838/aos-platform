# W5c6j Host 拓扑只读发现核验（2026-09-25）

方案 `4212f650` 先行、只读发现器及合同 `61ea5095`。未改 Host/worker/closure/真实 DB，未访问商城源行。

## 九步证据

1. 复习 `ar1_003` 受管目录、W5c5c/f/g、真实 closure 的 `FULL_MACHINE_HOST_TOPOLOGY` 缺口。
2. 文件级仅新增 `scripts/a0v_w5c6j_host_topology_discovery.py`、对应测试及本 verification。
3. 发现器只读取本机 exact launcher PID、W5c5f 受管目录结论、目标数据库已知登录的 `pg_stat_activity` 会话计数，不输出 argv/SQL/client IP/凭据。真实读回 `LOCAL_AND_MANAGED_SIGNALS_ONLY_INCOMPLETE_TOPOLOGY`，已知 launcher 0、已知登录会话 0、remote 0、unknown 0；此 0 不能排除非受管/其他机器。
4. 分类对未知/目录漂移冻结，对已知进程/会话输出阻断态；全部输出 `automaticAction=false`、`topologyComplete=false`、`closureAuthorized=false`。专项 **4 passed**。
5. W5c5k–z 加 W5c6a–j 累计 **71 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。发现器不能把单机/受管快照升级为全机权威；不调用 closure、不迁移真实 `a0v_093/094`。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6k：对跨机器 Host inventory 的权威来源/心跳 TTL/身份历史做架构方案与无效应合同；不能排除非受管 Host 则持续 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
