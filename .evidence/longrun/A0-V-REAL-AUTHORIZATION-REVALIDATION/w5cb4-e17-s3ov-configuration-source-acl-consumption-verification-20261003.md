# W5CB4 E17-s3o-v｜原 Host 消费入口来源 ACL 漂移验证

日期：2026-10-03；方案：同前缀 `plan`。仅隔离 `aos-ar1c-pg` 的临时 schema 写入；当前权威库 `aos_current_preview_20260927` 只读，Host/worker/Provider 均不开。

## 结果与证据

| 检查 | 命令/事实 | 结果 |
|---|---|---|
| RED | `AOS_EXTENSION_PG_TEST=1 services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_configuration_stage_consumer_pg.py -k source_acl_drift_after_startup --tb=short --disable-warnings` | exit1。旧生产 `run_once` 未拦漂移，走到原 Plan 读取后抛 `psycopg.errors.InsufficientPrivilege: permission denied for table aip_responsibility_plan_head`。 |
| 最小实现 | 原预检 SQL 抽为 `configuration_source_acl_ready(conn)`，生产 `ConfigurationStageConsumer.run_once` 在原消费事务内、原处理前调用；失配抛 `PermissionError('configuration source issuer ACL drifted')`，事务回滚。固定 `public.` 三表不受请求参数控制。 | 对 ACL 漂移失败关闭；原 primitive 和四源内容读者未改。 |
| GREEN/相邻 | 上述测试加启动预检、原 primitive 消费及生产入口边界、Host 选择四文件合跑 | exit0，45 passed；新测试先断言收权后 ACL 合规，再 GRANT INSERT，生产入口拒绝，原请求 `requested`、配置行0。 |
| 静态 | `git diff --check -- <本波三文件>`、`python3 -m py_compile <本波三文件>` | exit0。 |
| 当前服务只读 | `curl http://127.0.0.1:8080/v1/health`、`/v1/ready`；`curl http://127.0.0.1:8434/aip/skill-publish`；`lsof -iTCP:18181 -sTCP:LISTEN` | 200、200、200；18181 无监听。`/health` 返回404是非约定路径，改用 `/v1/health` 后200。 |

## 一致性与剩余门

复核 231/栖月汇与 E17-s3o-u：新增检查只在生产 Host 原消费事务内执行，不写当前库、不接受 runtime 自签来源、不改变原请求状态与幂等键。浏览器操作对纯后端禁入门不适用；已有 Web 页面 HTTP200 只表明可达，不等于正式安装/首链。

独立冲突：把 `aos_runtime` 收成来源表只读后，原 `read_current_responsibility_plan_ref` 的 `FOR SHARE OF h` 报权限不足。故本波只证明漂移时零配置，**不宣称收权后正向配置通过**；后续需设计专用发行身份与能保持当前版本稳定的只读消费协议，并在隔离库验证。当前真实库三表仍有宽授权，新代码在真实实例继续失败关闭。启动预检到本次事务检查之间已封，事务内检查到后续 DBA 并发授权仍需正式 ACL 稳态/发行协议，不能声称绝对竞态消失。
