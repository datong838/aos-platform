# 只读启动代码检查点

当前Task/base AOS-001369，唯一writer codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2。复习231/164/当前01与06；七强一致投影CURRENT、memory-validate GREEN。原HEAD ebac8fd0，原维护151 migration终端已成功但acceptance失败，未重发迁移/服务。

根因：disabled/managed把原boot_tenant_catalogs放在legacy块而跳过，读路由依赖空目录会重写已存在meta_org/meta_workspace/meta_membership时间戳；相邻实际me读取进一步复现list_orgs_for_subject/org_name对已有saas/invite_only调用ensure_org，覆盖默认字段。修复：非legacy严格只读加载现有表，缺表/连接失败向外传播；使用原db.connect_read_only在第一条SQL前设置只读RR、无tenant继承且现有platform_role；legacy默认接口和memory分支保留。读取已有组织不重新ensure，不改显式创建/编辑逻辑。

新接口首RED 6failed（缺只读接口/启动路径）；实际启动分支+真实me/workspaces反例1failed5passed，明确persist禁止触发；最终final-r2.log 41passed1deselected2subtests17.87秒exit0。8新测试包括viewer不升owner、原组织名/策略和工作区保留、读取SQL仅SELECT、只读连接参数、缺表不DDL、三loader异常传播、memory不连接/legacy接口兼容。5模块AST与git diff --check通过。

路由全量原测试保留RED：期望4523而实际4560。独立加载HEAD原5模块与修复5模块，完整inventory JSON精确相等且两边4560（route-baseline-comparison.json），本改动未增删路由。全局conftest尝试5433一次性测试库时因该服务recovery失败，日志保留；最终纯读取测试显式禁dotenv/memory/--noconftest，未连接当前权威18435。带client的组织会员PG集成未在本Task通过，不宣称全套GREEN。

复审：原legacy schema/seed仅旧块；新strict读取异常导致启动拒绝，避免空目录后隐式bootstrap；无签名安装/权限/角色/DDL/业务源门放宽；没有将旧时间戳归一掉。三独立RR读取并非跨表同一快照，现有受控维护零业务写窗口下可用；长期并发缓存刷新不属此修复。当前服务仍运行旧进程，未部署此修复，真实3旧时间戳尚未恢复，完整维护Task/八页面/首链保持pending。

下一候选：1当前maintenance已登记的151 post-start失败修复（基于原journal/固定源身份/当前Task，不使用142预检重放）；2已登记withdrawal epoch原生运行/正式Source组合专项，需原Task及独立库权限，不授Host/Provider或当前库业务写。先完成1，保留2安全研发主线。
