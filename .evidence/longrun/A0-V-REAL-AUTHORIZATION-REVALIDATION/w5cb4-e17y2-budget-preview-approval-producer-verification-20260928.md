# W5CB4 E17-y2 预算首次激活预览与审批生产者验证

## 基线和范围

- `m1@91be173e`、authority `AOS-000839` 起步；复习 231-3/5/9 与本波文件级方案后编码。
- 新代码迁移头 `a0v_110`；当前权威卷 `aos-a0v-recovery-pg-data` 的库 `aos_current_preview_20260927` 仍为 `a0v_109`。本波没有迁移或写当前库，也不以旧进程证明新代码上线。
- 当前 `org-org/dev-project` 仅一个正式 owner，独立 checker 缺失；测试中的第二成员只存在于可销毁隔离 PG，不是正式批准。

## RED / GREEN

- 迁移测试先因四表缺失 RED；Store 测试先因模块缺失 RED。修复范围为四张不可变、强制 RLS、租户键表及预算专属 Store/HTTP 契约。
- `AOS_DOTENV_DISABLED=1 services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_budget_activation_store_pg.py services/aos-api/tests/aip/test_aip_budget_activation_migration_pg.py services/aos-api/tests/aip/test_aip_budget_activation_exposure_pg.py services/aos-api/tests/aip/test_aip_budget_activation_authority.py services/aos-api/tests/aip/test_aip_budget_api.py services/aos-api/tests/aip/test_aip_budget_store.py services/aos-api/tests/aip/test_aip_model_governance_policy_store.py`：35 passed，退出 0。
- `compileall -q`：退出 0；`alembic heads`：`a0v_110 (head)`；`git diff --check`：退出 0。
- 隔离 PG 验证了正式 OIDC subject 形状、当前 owner/admin 双人、预览完整额度/期间、精确 Draft/head/target、幂等、撤销、权限失效和 `active` 修订仍为 0；HTTP 负例验证 dev 身份拒绝、公开 active POST 保持 422。

## 复审与结论

- 预览和审批只证明未来预算条款由两个不同当前主体审阅，`externalUsageProven=false`、`activationEligible=false`；数据库约束禁止把外部用量事实改为 true。没有原子消费或 active Budget Receipt，故不得启动 Host/worker/Provider，也不得称首链完成。
- 当前正式库未应用 `a0v_110`，运行中的 8080 仍是先前加载版本。下一独立波先做最新一致备份、可恢复克隆全链、零执行窗口，再决定权威卷迁移及最新栈重启；缺任何条件就保持当前服务与禁入，不强启。
- 浏览器 pilot 本波不可用；没有新增截图或页面正向验收。商城源、旧 12 Run、`dev-org` 写和手工 `run_definition` 均未触碰。
