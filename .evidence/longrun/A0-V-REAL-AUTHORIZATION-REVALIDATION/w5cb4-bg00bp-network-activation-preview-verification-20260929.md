# W5CB4 BG-00bp｜NetworkPolicy 只读激活预览 verification

## 基线与规则

AGENTS.md、aos-engineering-delivery、231/231-5/231-9、BG-00bi/bj/bk/bm/bn/bo 已复习。m1 单写，未 push；不读商城源，不碰旧12 Run、230 L0、手工 Run。当前真实库只读，Host/worker/Provider 禁入。文件级方案先行 `887350f2`；实现 `9ac7e9e6`。

## RED → GREEN 与方案核对

- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_network_policy_activation_preview.py` 退出2，明确缺少服务模块。
- GREEN：新预览 + target + runtime guard API + network contracts 四组 `28 passed`，退出0；`compileall -q` 退出0，`git diff --cached --check` 退出0。
- 服务仅 scoped SELECT 当前 head 并核现有 exact active egress；返回当前 head、候选/精确目标 hash 和结构化 blocker，`activationAllowed=false` 恒定。测试连接若出现非 SELECT 会断言失败。`If-Match` 缺失路由返回400。原 active 发布正式审批 422 邻接测试保持通过。文本 `approvalRef` 不当作批准。
- 当前缺正式 ActionType/Producer、独立批准、同事务一次性消费，所有预览恒有 `FORMAL_PRODUCER_UNAVAILABLE` 与 `ATOMIC_APPROVAL_CONSUMER_UNAVAILABLE`；版本/修订漂移或 egress 缺失分别补阻断项。目标 hash 只在当前输入相容时返回，不能执行。

## 最新栈与真实库只读复核

- API PID 4620 SIGINT 后以最新 m1 重新启动 PID 6270；启动日志 `database=aos_current_preview_20260927`, `migrationMode=disabled`, `runtimeHost=0`, `workersEnabled=0`。`curl /v1/health`、`/v1/ready` 均200；OpenAPI 200/5,278,776字节，新路由存在；Web 8434 页面200；18181 无监听。
- `docker --context colima-aos-extension inspect aos-a0v-recovery-pg`：running，命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`。使用 `scripts.a0v_current_preview_bootstrap._connection_parameters()` 且 `conn.read_only=True`：`aos_current_preview_20260927@a0v_115`；`meta_action_type=0`、`aip_network_policy_head=0`、`aip_network_policy_revision=0`、`extension_runtime_binding=0`。
- 首次通用 `aos_api.db.connect()` 回读误连 `.env` 默认库，`SELECT alembic_version` 因表不存在退出1；仅只读查询，无写。之后改用当前栈专用连接并先核 `conn.info.dbname`，上述回读退出0；本次不把默认库当权威。
- 没有正式账号的实时策略预览交互，也没有 browser-pilot 截图；OpenAPI、单元/接口测试与 HTTP 健康不证明真实批准或首链。Web 页面200同理。

## 风险、下一波

预览是无锁快照；将来 Producer/批准/消费必须重新读取 current head、scope/成员、maker/checker、期限/撤销和依赖，并在同一事务一次性 Receipt 消费。下一波 BG-00bq：冻结正式 NetworkPolicy ActionType/Producer 精确元数据及合法管理身份来源，先在 test-only PG 验证，不改当前真库；随后独立 checker/原子消费/安全迁移。八配置、Owner/Host、自然首链仍 pending。
