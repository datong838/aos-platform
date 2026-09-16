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
