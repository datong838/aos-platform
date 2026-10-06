# 非 legacy 启动租户目录只读加载修复

依据231的迁移/真实验收门与164 v1.1 PG目录重启不丢约束。当前151迁移已实际完成，不重发原维护；原acceptance失败保留。读取路径 /v1/me、/v1/workspaces 依赖内存目录；disabled/managed 跳过 legacy 块内 boot，空缓存触发已有目录上重复 bootstrap/upsert，是三张表 updated_at 变化的具体路径，需隔离反例验证。

文件范围见当前 Task tenant-catalog-readonly-startup-20261006：main.py、tenant_catalog.py、orgs.py、membership.py、workspaces_catalog.py及精确新测试/本证据目录。独立于当前维护资源，禁止在此任务改真库、启动服务、开启Host/worker/Provider、push。

实现：legacy保持原best-effort schema/seed；非legacy在启动阶段调用boot_tenant_catalogs(read_only=True)，只probe已有表，不调用schema DDL。三个目录loader新增默认false的strict选项，strict使用READ ONLY事务并传播读取错误；不改原legacy调用兼容语义。目录加载失败拒绝启动，不能接受空缓存后隐式bootstrap。memory store不连接PG且保留原内存数据。

RED：真实loader连接替身只允许SET TRANSACTION READ ONLY和SELECT，加载既有org/workspace/viewer会员后调用页面核心查询，断言无persist/owner覆盖；缺表无DDL、各目录读取失败抛出、非legacy lifespan实际分支调用严格boot。GREEN及相邻memory边界/迁移/路由清单/组织会员工作区回归；检查方案自洽及默认legacy行为兼容。当前三个旧时间戳不通过归一隐藏，单独维护阶段再恢复/完整验证。回滚仅精确代码文件；不可回滚已成功151迁移或删除备份。

相邻RED补充：实际/v1/me调用org_name时，ensure_org默认参数会把已加载saas/invite_only改为standard/invite_or_apply，触发persist。org_name只在组织确实不存在时沿用原ensure；已有组织名称读取不修改属性。真实启动分支AST执行后调用实际me/workspaces读取，保留viewer与非默认组织设置。
测试隔离：全局conftest会尝试5433上创建一次性测试库，但该端口服务处于recovery，导致fixture错误；本任务新增逻辑为纯缓存/读取测试，使用--noconftest并禁dotenv、显式memory避免接入共享PG。原日志保留，不能宣称该整套通过；带client fixture的TWA集成回归留待隔离PG入口。
同一真实me反例再次定位list_orgs_for_subject也对已有组织调用ensure_org；同样限定为确实缺失才ensure，避免读取列表改写现有属性。不改显式ensure_org编辑语义，不新增开户/权限。

连接复审修订：db.py在进入connect_platform上下文前已执行encoding/ROLE SQL，不能此时再SET TRANSACTION READ ONLY。复用既有connect_read_only(inherit_scope=False, platform_role=True)，在第一条SQL前设置驱动只读与RR，不修改db.py或新建连接权限。测试必须验证调用此连接工厂且拒绝任何非SELECT；旧式仍使用原connect_platform。路由基线前后独立inventory完整JSON相等，均4560，旧4523期望失败保留。
