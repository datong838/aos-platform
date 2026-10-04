# b56 文件级方案｜专用低权安装命令身份隔离 RED

## 上位与现状

- 231-3 的 active 卸载须正式停用、排空、释放、同事务原 Installation 终态和 Receipt；不能给 runtime worker 终结权限。b55 当前库只读发现预览 `aos_app` 是超级用户，`ar2_018` 函数明确拒绝高权 session_user；`aos_runtime` 无函数 EXECUTE。当前真实库 a0v_135 只读，不改卷/角色。
- PG16 无卷隔离实验已证明 `GRANT aos_app TO 低权登录 WITH INHERIT FALSE, SET FALSE` 可同时令 `MEMBER=true`、`USAGE=false`、`SET=false`，仍未证明专用登录可通过显式最小 ACL 完成同事务卸载。

## 本波文件与步骤

1. 仅在 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py` 的既有完整迁移 fixture 上新增专用登录试验：动态角色，NOINHERIT/NOSUPERUSER/NOBYPASSRLS，app 成员 `INHERIT FALSE, SET FALSE`，不给 runtime 成员。先不授函数/表权限，证明实际卸载失败；随后只在隔离 schema 显式授函数及必需资产表权限，验证同一连接 `RuntimeUninstallGuard` + 资产终态 + constraint+commit。
2. 明确负门：专用登录不能 `SET ROLE aos_app`，不能继承 app 权限；`aos_runtime` 仍不能直调函数；异租户或不满足正式排空不得写 terminal Receipt。复用既有真实 PG 卸载迁移夹具；本波只证终态 Receipt，完整 Installation CommandReceipt 留独立后续联合夹具，不造假业务成功。
3. 若无最小 ACL 可行解，留下 RED 和精确错误，当前实例继续禁入，转可信 evaluator 独立代码项。若隔离 GREEN，仅冻结角色/GRANT 合同，生产迁移和 connection factory 留独立波；不把 test-only 登录接当前 API。

## 验证与边界

- 新专项及原 app/runtime 负门通过；`git diff --check`，与231-3及 b55 审计逐项复审。无卷 PG only，无当前库写，不开 Host/worker/Provider；Goal active、不 push。
