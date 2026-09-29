# W5CB4 BG-00bj｜NetworkPolicy 激活目标纯绑定验证

方案：`w5cb4-bg00bj-network-target-binding-plan-20260929.md`。只新增纯合同与测试，不修改 Store/HTTP/DB/运行实例。

1. RED：新增测试后运行 `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_network_policy_activation_target.py -q --tb=short --disable-warnings` 退出 2，集合阶段 `ModuleNotFoundError: aos_api.aip_network_policy_activation_target`；证明目标合同尚不存在。
2. 一次回归命令误填不存在的 `test_aip_network_policy_store_pg.py` 退出 4，无测试执行；改用现有精确路径 `test_aip_network_policy_store.py` 重跑。`services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_network_policy_activation_target.py services/aos-api/tests/aip/test_aip_policy_activation_action.py services/aos-api/tests/aip/test_aip_network_policy_store.py -q --tb=short --disable-warnings` 退出 0，18 passed / 7 warnings。
3. 测试覆盖确定性、固定 ActionType、租户/host/policyId/head 变化导致 hash 变化、错 revision/head 与 draft 拒绝。内容 hash 复用 Network Store canonical hash；固定绑定还包含完整 tenant、policy identity、目标修订和 head。`compileall -q` 与 `git diff --check` 退出 0。

方案一致性与风险：返回值冻结，但不读取数据库当前 head、不校验批准或 maker/checker、不形成可消费 Receipt；调用者未来必须在 Store 同事务锁下独立重算和核准，不能接受客户端传入 hash 即授权。当前五类新 active 门、真实 PG 只读、Host/worker/Provider 关闭；approved 安装 binding0、八候选0、首链 pending。下一波 BG-00bk 查正式 ActionType producer 与 NetworkPolicy 审批/产品预览的最小接入点，先设计精确目标消费，暂不开放 active。
