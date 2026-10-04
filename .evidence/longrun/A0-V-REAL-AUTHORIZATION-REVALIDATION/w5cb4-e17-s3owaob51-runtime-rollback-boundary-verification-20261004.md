# b51｜旧 rollback 运行安装绕路失败关闭

## 方案/代码复审

- 上位 231-3 要求 runtime 装卸由 RuntimeOperation/资源义务收敛，且明确不得用 rollback 冒充卸载。生产 `build_installation_service` 原已注入 `RuntimeUninstallGuard`，但 `_append_rollback` 未调用 guard，原 Store 允许 active→rolled_back；旧 `/bundle-installations/{id}/rollback` 路由仍可到此方法。
- 先写文件级计划；完整 signed Growth1.13 disposable PG/OCI 中以生产相同 guard 构造旧 rollback，RED exit1 `DID NOT RAISE RuntimeOperationRequiredError`：原调用确实成功，不是推测。最小生产改动：`_append_rollback` 在已锁安装/替换保护后调用 guard 的**只读** `before_rollback`；该方法用已校验的当前 `StoredCompositionLock`、既有 `legacy_content_predicate` 与 Registry hash/manifest 判定纯内容。运行成员、缺失/损坏来源均抛受控 `RUNTIME_OPERATION_REQUIRED`，由既有资产路由映射409；不执行运行资源清理，也不更改原 uninstall 命令。
- 修补后隔离签名运行安装 rollback 被拒，安装仍 active、current/active revision与ETag未变，命令 key Receipt0；异常对象 http_status409/code精确。另一真实 PG 仅 core 纯内容安装，在配置同一 guard 的服务中仍可 rollback→rolled_back/ETag6。无 migration、真库写、Host/worker/Provider启动。
- 本波避免用 rollback 造运行安装的“合法换代”测试；真正停用/卸载仍需 RuntimeOperation、审批/排空/资源义务。b48–b50 test-only 受限命令、可信 available 和正式三身份等未被此生产守卫解锁。

## 命令与退出码

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 AOS_EXTENSION_OCI_TEST=1 AOS_B51_RUNTIME_ROLLBACK=1 AOS_GROWTH113_SIGNED_RECEIPT=/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings --show-capture=no services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py` | 修补前 RED exit1 `DID NOT RAISE`；修补后 exit0，1 passed/7 warnings，追加409精确断言再复跑 exit0。 |
| 同完整 signed 命令去掉 b51 模式 | exit0，1 passed/7 warnings，原路径未回退。 |
| `AOS_DOTENV_DISABLED=1 AOS_EXTENSION_PG_TEST=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --tb=short --disable-warnings services/aos-api/tests/asset_registry/test_m5_ecommerce_rollback_isolation_pg.py services/aos-api/tests/asset_registry/test_installation_service.py services/aos-api/tests/extension_runtime/test_runtime_uninstall_approved.py` | exit0，7 passed/7 warnings；其中新增纯内容+guard真实PG正向1 passed。 |
| b37/b45/Release 相邻三文件（与 b50 verification 相同命令） | exit0，32 passed/2 strict xfailed/7 warnings。 |
| `compileall -q` 两生产与两测试文件、`git diff --check` | exit0。 |

## 剩余风险与下一步

- 生产 API 进程需加载本提交后再复核只读健康/页面和受控错误；当前正式实例依然缺 OIDC/Issuer/Reader/Owner、active Growth1.13、八配置/六 Binding/首链。当前库135只读、Host/worker/Provider关。
- b52 在合法 RuntimeOperation 收敛路径找可执行的安装换代生产者，或继续独立可信 evaluator/角色权限施工；不能从本波拒绝旧 rollback 推断卸载、重装或第一经营闭环完成。唯一136/当前卷切换另波须新备份、全恢复、零执行窗口。
