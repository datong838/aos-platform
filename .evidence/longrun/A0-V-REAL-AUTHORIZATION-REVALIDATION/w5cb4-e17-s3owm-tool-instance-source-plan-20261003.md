# W5CB4 E17-s3o-w-m｜原 ToolBinding 当前 Agent 来源门

日期 2026-10-03，基线 `m1@513331ba`、Authority `AOS-001223`。复习 231/231-9、W-L20、D-wave s3o-w-l、原 Assignee Store/Resolver、AgentRegistry 与 RegistryReceipt。当前真实库只读、Host/worker/Provider关闭。Tool 的正式 owner、批准/安装引用、专用 issuer/Receipt 与 runtime ACL 切换仍未解决，不以本切片冒充正式 ToolBinding 发行。

## 原入口与最小合同

`AipAssigneeResolutionStore.upsert_tool_binding` 目前在同租户表直接写 active ToolBinding，未核 `agent_instance_id` 是否存在/active；只有后续 `resolve` 会检查。旧 `test_e17_s3oq` 使用不存在的 test-only AgentID，因此掩盖了发行时伪 active 的缺口。原 RegistryReceipt xfail 仍证明没有同事务发行 Receipt；暂不向可伪造的当前宽 ACL 加表面回执。

本切片只加发布前置：**active** 请求必须在同一租户查到 `aip_agent_instance.status='active'`；缺失、非 active 或仅其它租户存在，原事务拒绝且无 ToolBinding 行。`disabled` 更新保留可撤销旧绑定的路径，不因 Agent 已停用而拦撤销。发行后若 Agent 状态改变，原 `resolve` 仍重查，不能把这一发行检查当长期运行许可。本次不引入 Agent version 字段、Tool 来源伪造、公共协议或 migration。

## 文件级 RED→最小实现→回归

1. 新增 `services/aos-api/tests/aip/test_e17_s3owm_tool_instance_source_pg.py`：隔离 PG 只向 `org-org/dev-project` 写 test-only Agent，用原 Store 测租户范围内缺失/非 active Agent 的 active 请求失败且 binding 行0；本租户 active Agent 正向、停用旧 binding 与解析后撤销禁入。查询严格带双租户键；不向 `dev-org` 写测试数据。先 RED。
2. 最小改 `services/aos-api/aos_api/aip_assignee_resolution_store.py`：在原 upsert 同事务写前做同租户 active Agent 存在检查，抛结构化 `AipAssigneeResolutionBlocked`；`routers/aip_assignee_authority.py` 只映射该 blocker 为 409，不改角色/OIDC 边界。原 `test_e17_s3oq_tool_binding_issuance_pg.py` 先用真正 test-only active Agent fixture 替代不存在 ID，保留版本门语义；旧 `s3or` xfail 应创建测试 Agent 后仍留 Receipt 缺口。
3. 专项、W-L20/W6/Registry相邻回归、py_compile、diff check；审查正反路径及当前库零写。无 UI 或 migration 变更，浏览器适用性低；当前实例仍无正式身份和 Tool 来源，不发 live 写请求。

## 后续正式发行合同

独立下一波仍须决定 durable Tool sourceRef 与 exact actor/批准/安装身份，再在 disposable PG 上证明独立非 owner issuer、同事务 RegistryReceipt/idempotency、普通 runtime 两表收权、当前性消费。现有内存 `ToolRegistry`、W-T4 capability tool 展示卡和 test-only 字符串都不是该正式来源；BI Plan issuer 安装事务身份另列可独立项。真库切换要新全备、全链克隆与零执行窗口，不在本波执行。
