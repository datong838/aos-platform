# SC4-5L6Y 完整源组的产品调度设计

2026-09-16，承接W/X与原snapshot-resume-design.md l6g。Rules：原Owner、Receipt-first、双租户、单写m1、最小变化；不push、230L0挂起；方案不是主库完成证据。

## 产品问题与目标

当前真实库只有P01/P02图、控制和调度。单路execute_schedule可以产生商品事件，却不能支持经营分析所需十二源同事务快照。现有完整组Ingress/Completion可执行，但组测试通过fixture直接INSERT十二条运行记录，没有正式产品调度组入口。这是尚未闭合的产品缺口，不能靠部署脚本插运行行弥补。

用户配置一次已安装领域包的源组、权限、额度和周期，系统按周期领取完整组、读取一次一致快照、完成对象/关系/必要清退，并从真实变化自然派发分析。来源配置或任一控制过期/禁用时整组停止。无新变化时不制造经营任务。重复tick/进程重启必须读取原组回执，不创建第二组或盲目重读。

## 原接口与不可跳过的约束

- PipelineScheduleControlOwner绑定独立源调度与exact控制；其原schedule行锁是领取和首次绑定的共同边界。
- PipelineSnapshotGroupOwner校验同安装、代次、执行epoch、配置、包、source、schema、masking和公共有效窗口；同组禁止重复pipeline/table。
- ControlledSnapshotGroupIngress先提交原source claims再真实read，随后原输入整体提交；claim已存在而input不存在属于未知，绝不重读。
- PipelineSnapshotGroupCompletion完成原对象/关系/清退并一次收尾十二路调度；部分Store结果由原Receipt恢复。
- 不能在新调度层提前reserve原source group claim，否则Ingress将首次读取误认为未知。新调度领取回执与原source claim是两个不同边界，必须显式区分。

## 分阶段实施与文件

Y1 原子运行领取：新增pipeline_snapshot_schedule_claim.py及对应PG测试；新增a0v_062_snapshot_schedule_claim.py持久化不可变调度组领取回执（同scope/group唯一、绑定组request hash、所有exact schedule binding与controlRef、同一slot、服务端run IDs）。运行行与该回执同事务创建；十二路任一路冲突/控制不符全部回滚。原source claims保持0，后续仅原Ingress有权首次领取source。迁移只用于隔离验证，主库升级另波先克隆验证与备份。

Y2 配置与控制：新增租户/安装绑定的源组配置Revision/Head及原Owner/API（开工前补字段、具体迁移文件与UI路径）。完整成员取已安装导出的源组需求，要求十二源映射、同actor当前权限和每一路已审批控制；cron、enabled、成员与policy exact ref版本化。配置停止先围栏新领取，再处理原在途组；不能删除历史回执。组成员不再被单路cron重复执行，单路手工运行也必须受组归属围栏。

Y3 执行与恢复：新增pipeline_snapshot_schedule_runtime.py，复用原Ingress→原Completion；组ID及run IDs来自Y1不可变回执，原input已存在只读恢复，无input且source claim已存在明确unknown。仅调度组领取提交、尚无source claim时允许继续原首次prepare。跨控制失效保持停止；不得将unknown改成失败后新建组绕过。

Y4 生命周期接线：PipelineControlServices、原cron worker与受保护路由接入组Owner/runtime。安装禁入/禁用/卸载必须阻止新运行；重装须新current配置，不复用旧权限。与原单路调度共存，未加入组的调度行为不变。

Y4代码复核登记于sc4-5l6y4-snapshot-worker-lifecycle-review.md：现有asyncio.to_thread在Task取消后不保证同步执行停止，需显式停止传播和实际退出核验；周期领取必须防止上一组unknown时通过新slot绕过。该记录为实施前发现；截至 b4314cf0，Y4a–Y4d3b2 代码及隔离验证已完成，详见 managed-worker 实施方案。主库仍未部署/启用，真实验收留 Y6。

Y5 真实配置：从当前签名包导出的十二源Mapping/源schema读取能力自动生成可审查配置，经原选择/控制审批Owner建立P01–P12图与绑定；不能修改源库数据、不能扩大masking、不能靠owner SQL绕过配置。实际源缺失或不符合质量时如实阻断。

Y6 克隆迁移/恢复演练→主库受控升级→真实完整组观察。主库原J失败Run保持原事实；Z的正式需求/任务恢复合同完成前，不以新Run代替它宣称已恢复。

## Y1 细化合同（实施前仍需核对原迁移约束）

可信调度服务传同一scope、actor、规范group UUID、带时区slot和十二个当前ScheduleControlBinding。固定顺序锁schedule行，逐条核enabled/ingest/pipeline以及current exact binding；在原GroupOwner current守卫内要求完整canonical源集合及共同窗口。服务端生成run IDs；同slot已有任何其他领取拒绝，不接管。先查询同group回执：exact同request回放返回原ids，不同request拒绝；无回执才插入全部原meta_schedule_run与领取回执。未知提交只用原group/request读回，不改key。

新记录是调度领取证据，不是读取授权；使用时继续检查原current源控制。新表RLS强制双租户、不可UPDATE/DELETE/TRUNCATE，runtime仅SELECT/INSERT；成员FK到原run及schedule绑定，检查成员完整和scope。不得接受浏览器传run ID或success。

## 验收

按Y1–Y6连续登记：原领取原子性、重复零新增、部分冲突整体回滚、控制/租户/角色错配拒绝；每组最多一次真实源读取；未知结果不重发；停止和卸载禁入；完整图/调度经产品Owner创建；最终必须真实数据变化触发首链并产出建议，不能以组服务测试代替经营验收。

## Y1 数据结构与实现约束补充

新增两个专用表：pipeline_snapshot_schedule_claim（scope/group UUID、actor、scheduled_for、trigger、request_hash、request、content_hash、record、created_at）；pipeline_snapshot_schedule_member（scope/group、ordinal 1..12、schedule_id、binding_id/revision/hash、pipeline_id、controlRef字段或原绑定引用、run_id）。成员唯一约束覆盖同group的schedule/run，FK分别绑定原ScheduleControlBinding和meta_schedule_run；deferred约束验证正好12成员、ordinal完整、成员record与主表一致、原run的schedule/slot/trigger一致。主表及成员表均强制RLS且不可变。请求哈希不含服务端随机run IDs，回执哈希含全部原run IDs；同group重放必须同时复验两种hash和成员索引。

运行领取遵守原control→schedule锁顺序：先在原完整GroupOwner校验current、canonical pipeline/objectType全覆盖；再按schedule_id稳定排序锁原meta_schedule，核对每条最新binding精确引用与actor。独立单源运行的同slot冲突依旧由原PK约束保护，错误回滚全部新行。首次领取只接受服务器当前UTC分钟或固定服务端manual slot；旧slot只允许读取已存在exact组回执。不得凭客户端过去/未来slot创造历史运行。

Y1测试使用隔离完整schema，明确清除原native fixture尚未消费的测试run行后，经原ScheduleControlOwner建立12条当前绑定，再由新Owner真正创建12运行并验回执；这种测试清理不允许用于主库。正向断言原source claims/input均仍0，证明领取运行没有提前取得源调用资格。源调用与重启恢复留Y3原Ingress做最终判断。

Y1补充验收文件：services/aos-api/tests/extension_runtime/test_pipeline_snapshot_schedule_recovery_pg.py。每例私有完整数据库，实际提交原12运行及回执后模拟响应丢失，新连接/new Owner读回同回执并在current控制下重放，验证零新运行/零source claims。新增DB直接不完整回执拒绝测试，不把Owner层拒绝当作数据库约束已验收。

Y1复核补强：新Owner SQL及约束函数固定public权威表，函数固定pg_catalog/public/pg_temp查找顺序；运行角色创建同名临时表不能替代回执或绕过完整性检查。新增同名临时表Red/Green验证。旧专用schema回归需AOS_EXTENSION_PG_TEST和18432独立库，首次未显式启用的31 skipped不算通过；新Owner与真实提交读回9项已通过，最终增加原native完整组Owner累计回归。

## Y1 验收结果（2026-09-16）

实现新a0v_062两表与deferred完整性约束、原Owner整体领取、exact当前绑定/十二源覆盖、一次事务十二运行、同group回执重放、source claims仍0。新Owner/跨连接提交恢复/同名临时表/原完整组Owner累计14 passed / 12.07秒（/tmp/aos-group-schedule-final-v2.log）；显式启用18432独立测试库后，原单路调度绑定、CAS、claim行锁与运行领取31 passed / 8.35秒（/tmp/aos-group-schedule-legacy.log）。最初31 skipped已补跑，不能计为通过两次。Red为缺少新Owner模块，以及同名临时表使原read错误返回None；后者由固定public查询与约束函数查找路径修复。

git diff --check通过。新表仅在隔离测试库迁移，主库仍a0v_061。新Owner没有远程读取、没有创建SourceClaim，也未被cron/API自动调用；此结果只完成Y1。下一波Y2需安装绑定的正式组配置、可禁入/停用和成员单路调度围栏，随后Y3运行恢复与Y4生命周期接线。J原失败Run未被替代或回写。

Y2具体配置/启停/退役、停用不回落单路、锁序和文件清单见sc4-5l6y2-snapshot-schedule-configuration-plan.md。状态分disabled/enabled/retired；member归属只在确认无在途/未知运行的retire中释放，不能disable后被单路cron接管。Y2a/b/c分别收口存储Owner、API与围栏、产品入口验收，不以其中一个完成代替整体产品可用。

## Y3恢复边界增补（2026-09-16）

Y3a已引入exact enabled配置v2领取，Y3b补每事务守卫与原Ingress/Completion接线。新增Y3c正式组窗口续期恢复Owner/Receipt：原组已领取且有input时，单路既有窗口续期机制不能自动越过旧组exact definitionRef；需要明确关联原group、原input、旧定义及同业务上下文的新窗口控制并经原权限核验。未完成前到期禁入，不改历史、不用新Run冒充恢复。Y3c须在Y4/Y6真实恢复验收前完成；无原input的unknown仍禁止重新读取。

Y3b-2完整runtime接线暴露重复current校验成本，新增Y3b-3性能波次（sc4-5l6y3b3-snapshot-guard-cost-plan.md），排在Y3c正式续期恢复前。以原调用计数、数据库往返与完整真实PG/Store耗时验证改进，不能以跳过权限、跨事务缓存许可或提高递归上限替代。Y3c草案另见sc4-5l6y3c-saved-group-renewal-design.md，明确未实现事项和原回执不变边界。
