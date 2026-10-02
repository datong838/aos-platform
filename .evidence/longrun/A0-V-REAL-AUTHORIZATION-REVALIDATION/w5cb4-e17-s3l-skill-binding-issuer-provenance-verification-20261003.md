# E17-s3l SkillBinding 来源门：隔离 RED、修复与复审

基线 `m1@608aab2e`、Authority `AOS-001182`；方案先于代码：`w5cb4-e17-s3l-skill-binding-issuer-provenance-plan-20261003.md`。当前真库 `aos_current_preview_20260927@a0v_135` 仅做权限只读查询，回 `aos_runtime` 对 `aip_skill_binding` SELECT/INSERT/UPDATE 为 `t|t|t`。新测试只走 conftest 自动建/删 `aos_test_*_ti4_test`，正向租户 org-org/dev-project、dev-org 仅错租户只读。

## RED → GREEN

- 先沿 s3k 两负例再加第三负例：直接插 active/available/未过期且有 snapshot 的 Binding，但引用 draft Skill、没有原 Registry Receipt；旧 Plan `created.readiness=READY`，新断言期望 BLOCKED，`1 failed/2 passed`、pytest exit1。旧码在该断言前停止，**未证明旧码实际上成功 freeze**。
- 原读取点增加精确当前 published Skill 与租户、同 Skill 家族最新生命周期仍 published、同租户同 binding ID 的 `skill_binding.create/evaluate/update` applied Receipt 校验；来源不合格报 `SKILL_BINDING_SOURCE_INVALID`，不从该 Binding 贡献能力。仍按原门先检 readiness/snapshot/expiry，原能力 operational/health/fresh 判断不变。若全部来源不合格，保留能力缺口诊断但来源 blocker 始终关闭该职责；uncovered 不重复。只改生产 `aip_production_contract_store.py` 与 `test_w2b_production_contract_store.py`。
- 新增第四负例：**手工构造**符合表字段的 published Skill 与 active/available/fresh Binding，但无三份 Registry Receipt；它是攻击测试输入，绝非正式发布。四负例 `4 passed/14 deselected/7 warnings`，pytest exit0；Plan blocked、freeze 拒绝、freeze Receipt0、head不动、dev-org 对 Plan ID count0。原 `test_w2b` + Binding readiness 相邻 `22 passed/7 warnings` exit0；Registry 原测试单独 `5 passed/7 warnings` exit0；BI 权威原测试单独 `34 passed/7 warnings` exit0。`py_compile`、目标 diff check exit0。

## 测试编排与局限

- 一次并行 PG 回归的 `test_w2b` 组在测试库迁移 setup 报21 errors；并行的另组5 passed。随后目标用例与22项相邻串行复跑均退出0。另一次 BI 用例路径误写在 `tests/aip/`，pytest exit4；改为实际 `tests/test_ecommerce_business_investigation_aip_authority.py` 后34 passed。published 负例初始违反原数据库 provenance/LogicRef 形状约束，修正攻击夹具后才得结论，均未靠放宽生产约束消红。
- 所有新增正反证是**负例**；`_CoverageConnection` 的 `source_valid=True` 仅保留既有能力覆盖单元夹具，不是正式签名绑定正向验收。当前没有六个原正式 active SkillBinding、签名冻结 Plan 或自然业务首链；没有在真实库写 Plan/freeze。
- 当前 `aos_runtime` 可以写 Binding，且对 Registry Receipt 有 INSERT；应用层 JOIN Receipt 防止误把无来源直插行当正式绑定，**不能对抗持有此数据库角色的伪造者**。要建立独立强签发边界，须另波设计受限 issuer/ACL、迁移和当前卷备份/克隆全链，不在本波调整真实 DB。`assigneeResolutionReceiptId` 分支用另一 canonical Receipt，本波未改它；应在独立波核其签发和失效语义。

## 提交后在线加载

`m1@3b499356` 后，原签名预览启动器预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、publishedVersions4/runtimeBindings0；原卷库 `aos_current_preview_20260927@a0v_135` 只读回读，今日完整备份 SHA256 再核 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，均退出0。原 launchd API 项在 `bootout` exit0、确认服务和8080退出后，用同一 plist `bootstrap` exit0；新 API PID33442，Web PID31986 保持。18435/8080/8434 LISTEN，18181不监听；health/ready/OpenAPI/页面 HTTP200。新进程日志 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`、Host inactive `DISABLED`。浏览器 CUA 在原 org-org/dev-project 页回读 AX 无变化，截图显示37条、0已发布；未触发真实 Plan/freeze，**不作为来源门正式正向或首链完成证据**。
