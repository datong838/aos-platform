# BG00GW-c verification

基线 AOS-001067 / 075193f4；本波只新增真实临时PG联合测试，没有修改业务逻辑/权限/schema。

- 初次写文件命令cwd拼接错误，文件未创建，pytest退出4（找不到文件）；已纠正到API相对tests目录。不是实现RED。
- 专项：`.venv/bin/python -m pytest tests/extension_runtime/test_growth_approval_handoff_source_pg.py -q --tb=short`，1passed/4.70s/exit0，零跳过。
- 累计：上述文件加tests/test_ecommerce_analyst_growth_plan_approval.py、tests/extension_runtime/test_ecommerce_review_advance_host.py、tests/extension_runtime/test_analyst_growth_plan_approval_rule.py，30passed/4.79s/exit0，零跳过。
- py_compile / git diff --check均exit0。

## 真实证明范围

标准conftest创建全迁移一次性aos_test_*_ti4_test库，测试显式断言数据库名称。fixture草稿经原publish_plan；原approve服务创建相邻approved；原_revalidate_growth_plan使用真实SQL在aos_runtime角色下消费原head/revision/Receipt。无monkeypatch关键校验。
草稿直接交Handoff来源reader拒绝；批准后读取成功，priorRef精确回draft；重复approve只保留两个revision与两个原OwnerReceipt；错hash、旧draft、dev-org只读负例均拒绝。生成正文、真人HTTP鉴权、阶段Eval及完整Handoff均未验证；fixture引用不代表客户来源。原累计文件中的mock测试只证明既有单元逻辑，不计真实联合。

## 下一步判定

已排除“批准版本格式/Receipt与Host不兼容”的疑点，不能重造批准服务。真实缺口仍是：accepted decision绑定旧draft→批准后继priorRef；旧Handoff依赖OPEN ReviewIssue及四类Artifact，与现有阶段产物不一致。下一波明确原产品批准意图的消费路径，复用已证实的Owner批准来源和Task/Brief，不制造Issue或Artifact。
公共subject-review签名用途等待裁决；本波无当前库连接/迁移/重启、Host/worker/Provider、商城读取或旧Run重放，无push。无UI变更，不适用浏览器。

## 日志SHA256
- `/tmp/aos-gwc-source.log`: `b89049151e31dba52140a34468971e19be99986d145ad478793c3b51918f685f`
- `/tmp/aos-gwc-regression.log`: `6552655aa0d9cdcfabbe63e343f246d6a9365b6c77d2cae5384ca12f2a22b60b`
