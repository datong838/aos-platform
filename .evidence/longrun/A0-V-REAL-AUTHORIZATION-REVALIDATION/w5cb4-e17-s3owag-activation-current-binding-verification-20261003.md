# s3o-w-ag｜Agent 激活时绑定现时性事务门验证

## 上位方案与 RED

依据 231-9、BIND-1 六数字同事/CapabilityBinding 实施清单及本波文件级 plan。当前六 AgentInstance 为 provisioning，模板来源 Growth1.11；CapabilityBinding0、ToolBinding0、正式 BI OS/DB/IdP 身份缺失。旧激活实现将绑定读和 Instance/Receipt 写拆成两个事务。

新增一次性 PG 测试先在原两步间确定性撤销绑定：`pytest -q ...test_aip_agent_instance_activation_current_binding_pg.py` 输出 `1 failed, 1 passed`、退出1，失败为 `DID NOT RAISE AipAgentRegistryTransitionBlocked`，证明旧代码在绑定撤销后仍激活。没有在当前真库运行写测试。

## 最小实现与验证

`AipAgentRegistryStore.update_instance()` 增仅内部可注入的 `before_update`；原幂等 Receipt 回放先于该检查，其他调用者默认行为不变。激活服务保留原早期预检，在原 Store 写事务内重查 exact published Template 和全部同租户 Binding，`FOR SHARE` 锁行至 Instance CAS 更新与原 RegistryReceipt 同事务提交。无效时整事务回滚。

| 命令/验证 | 新鲜输出 |
| --- | --- |
| Agent registry Store/合同/激活专项和新 PG 竞态 | 26 passed，退出0 |
| `test_phase3_aip_agents.py` 路由相邻回归 | 7 passed，退出0 |
| `python -m py_compile` 三个改动 Python 文件、`git diff --check` | 无错误，退出0 |
| 新 PG 负例 | 预检后撤销时保持 provisioning、`agent_instance.update` Receipt0 |
| 新 PG 正例与锁竞争 | 合法绑定产生原 Receipt；锁内并发撤销因 `lock_timeout=200ms` 拒绝，提交后撤销可成功；原同键只回原 Receipt |
| 当前库只读对账 | `aos_current_preview_20260927@a0v_135`；org-org AgentInstance6、active0、CapabilityBinding0、RegistryReceipt6；一次性 `aos_test_*_ti4_test` 库残留0 |

## 一致性与限制

本改动只修“激活当下”的绑定现时性事务竞态；当前 six provisioning 不会被自动激活。原模板来源仍 Growth1.11，当前签名 Growth1.13 及六个正式绑定/正式身份须独立完成；运行读者自身的撤销检查仍须保留。测试库只用于证实事务行为，不能充正式业务资格。当前真实库未迁移、未写；Host/worker/Provider继续关闭，自然首链 pending。
