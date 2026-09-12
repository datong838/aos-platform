# 正式调度入口接入代码验证

2026-09-13；基线e7c35209；m1独占主A0-V Lease。

qyh手动/恢复/Cron读取不可变计划关联，有绑定但无exact服务器工厂时拒绝，不能回退旧执行。绑定被替换时原子领取前拒绝。新增pipeline_schedule_claim.py：runtime事务持有meta_schedule行锁，核对enabled/ingest及完整关联后领取Run；旧恢复也走同一事务。首次ScheduleControlBinding拒绝running或停止结果未确认的旧任务，避免首次绑定与旧领取交错。已有绑定修订继续由受控各阶段检查。无绑定普通计划保留原执行语义，但必须能检查关联表；主库025部署是重载此代码的前置。

网页手动/恢复从Request.app.state传入工厂，Cron从lifespan app.state传同一工厂。源/控制对象不能由HTTP body注入。手动控制冲突409/权限403/服务异常503脱敏提示。正式运行仍原线程和原ScheduleRun事实，不跳过原pipeline禁用预检。服务当前性和claim_recovery使用真实PG Owner/Run/原输入/恢复Receipt验证；签名资产与外部源为明确fixture。

RED：首次绑定4项反例原实现均未拒绝；新增resolver3项缺入口；qyh2项缺factory参数；网页2项未传服务，手动2项未脱敏。最小修复后最终联合85 passed（运行资源、qyh、HTTP、绑定Owner、原子领取、受控事务、服务恢复和wave_ext租户测试）。PG两连接验证计划行锁串行：旧领取先获得锁并置running，首次绑定随后拒绝；绑定先完成，则旧领取拒绝。原run恢复成功只增加一条恢复Receipt；同claim重放false；源调用维持1。未知stopped拒绝且无Receipt。

真实本机5173/ontology、8434/、18181/v1/health均HTTP200；这只证明正在运行的旧服务可达，不代表新代码已部署。main仍024，025没有部署，无新真实source/approval/P01启用，未形成经营首链。整体阶段仍受控真实数据接入。

下一波：为025新建独立部署Lease与脚本，现状指纹、备份、独立库恢复升级验证，再主库升级；重载前核对生产runtime角色和数据权限、主API/独立Host单写者；随后真实SourceSelection/Control/计划绑定与激活路径验收。需持续审计其他Pipeline直接执行入口是否能绕过已绑定计划；该审计未完成，不作发布结论。前波记录的7项旧目录种子/工作区测试失败仍保留。
