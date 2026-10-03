# s3o-w-ah｜六 Agent 来源与激活时钟门验证

## 来源对账

当前真实库只读查询：`aos_current_preview_20260927@a0v_135`；org-org/dev-project 六 AgentInstance 全 provisioning、active0；六个 published AgentTemplate 的 `source_ref.revision=1.11.0`；CapabilityBinding0。当前安装的签名 Growth1.13 由最新 HTTP 预检核验，但 AIP 定义发布器 `CURRENT_SIGNED_CANDIDATE_VERSION=1.11.0`、定义门禁止混合来源。仓内候选 1.11/1.13 的 six-coworkers、capability catalog、37 logic、AIP runtime policies 四份文件 SHA256 各自相同。此为内容比较，不等于已取得 1.13 AIP 定义的独立正式发布 Receipt；未改旧不可变定义、未批量激活六 Agent。

## RED、最小修复及回归

新增一次性 PG 负例令 `occurred_at` 早于 Binding 到期，原写事务发生于到期之后。原代码仍激活：`1 failed`，`DID NOT RAISE AipAgentRegistryTransitionBlocked`，退出1。只在原同事务 `FOR SHARE` 锁定模板/Binding 后，用数据库 `clock_timestamp()` 与请求时点取较晚值再验 expiry；Instance CAS/RegistryReceipt、默认 Store 和公共 DTO 未改。

| 检查 | 新鲜结果 |
| --- | --- |
| Agent 激活 PG/Service/Store/合同及 Phase3 路由相邻回归 | `34 passed`，退出0；首次命令误写不存在的 `test_aip_agent_registry_store_pg.py` 退出4，按 `rg --files` 找到实际文件后修正命令，未改代码来掩盖。 |
| 到期负例 | 激活拒绝；Instance 保持 provisioning、`agent_instance.update` Receipt0。 |
| 撤权/合法/并发锁/重放旧正反 | 现有四个 PG 测试继续通过，原合法 Receipt 与同键回放行为保留。 |
| 编译/差异 | `python -m py_compile` 两文件、`git diff --check` 均退出0。 |
| 当前库只读对账 | `aos_current_preview_20260927@a0v_135`；Agent6/active0、CapabilityBinding0；一次性 `aos_test_*_ti4_test` 残留0，查询退出0。 |

修复仅封堵写事务时已过期的 Binding。当前正式 Provider/Route/Eval/Tool/Budget 等依赖、六 Binding 和身份仍缺，不能据此启用当前实例或自然首链。真正服务运行后仍需以新进程/浏览器验证失败封闭。
