# 撤回资格提示验证｜2026-09-13

Rules：复用既有交付规范和231-9/BG-01；m1单写者、不push、230 L0挂起；方案先行、最小更改。基线07b8d17c。

第1/6步：复核030原子撤回、GET登记发现及实际源表ACL，当前cutover只允许maintainer读取，调度/command/dispatch沿runtime现有权限。
第2/6步：扩充first-registration-withdrawal-design.md。提示不是授权，写入仍复验权限/CAS/原快照及全部历史。
第3/6步：资格测试RED 8 failed、3 passed；新增ecommerce_growth_withdrawal_status.py固定读取器并接到唯一登记状态分支。
第4/6步：38项真实隔离PG测试通过；补充RLS关闭拒绝、cutover/调度/command/快照变动均不可撤回。
第5/6步：82 passed、7 warnings、7.83s；包括提示生成后安装etag变化导致正式撤回拒绝、多原登记歧义不猜测最新。日志/tmp/a0v-status-hint-final.log。AR2扫描1822、分类158、迁移93；五类错误为空。memory-validate GREEN；diff --check通过。
第6/6步：本片交付后自动转入前端合同/客户端与安装详情页入口；随后主库独立连接/迁移与实际产品路径验收。BG-01整体保持未完成。

响应新增expectedInstallationEtag、withdrawalReason；唯一未使用登记允许显示withdraw，其余不显示动作。executable始终false。读取强制检查所有相关表RLS和非owner/非super连接，临时maintainer只读取cutover后立即回runtime；不执行写函数、不新增数据库权限/迁移/能力调用。读取失败不能默认unused。前端还未接线，运行API未部署此新代码，主库仍不能因此宣称可用。

隔离PG中当前安装store/权限组合仍用明确fixture，其余SQL/RLS/原子Receipt为真实执行。主库当前权限组合、前端浏览器、完整首链、八场景和连续经营观察均未验收。模型未知调用未重发，费用/预算边界未绕过，既有数据未变更。
