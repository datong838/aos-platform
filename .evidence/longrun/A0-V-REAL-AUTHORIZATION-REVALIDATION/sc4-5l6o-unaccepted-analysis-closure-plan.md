# 未接收事件分析的正式结案

## 实证与边界
G事件入口fence成功（group13）；shrink因21个unknown dispatch attempts被正确拒绝。待处理109项本身不阻塞该drain检查，保持原历史。旧shrink意图保存，不重发。主库当前a0v_059。
仅适用 ProductEventAnalysisService._handle 的自动分析初始化：纯安装包计算后，_initialize、runtime Receipt、pending data准备位于同一事务；原event-control dispatch在_phase入口锁定并在末尾复核，任何异常整体回滚。对其他能力调用/外部动作不能推断无副作用。

## 方案
1. 新增领域结案服务和a0v_060迁移：保留原occurrence/attempt，新状态cancelled（occurrence）和closed_unaccepted（attempt），独立不可变结案Receipt记录原状态、安装代次/epoch、原target key、fence Receipt及目标未接收证明。
2. 只能org/project当前管理员调用；严格固定operation=ecommerce_growth_analysis_advance、trigger=event。锁当前event-control dispatch及runtime，要求当前entry已fenced、同安装代次/epoch、所有相关事件binding禁用；读并校验真实fence Receipt。持有与原handler相同dispatch锁，等待任何已进入事务的handler结束。
3. 在锁内核对选定occurrence needs_attention、全部attempt unknown且claim lease过期、没有running runtime invocation；按target key查目标analysis runtime Receipt，按确定性run_id/trigger_key查BusinessInvestigationRun，任何结果存在都拒绝并转目标Receipt核对，不做取消。
4. 原handler任何未来执行都会被仍fenced的event入口拒绝；closed_unaccepted不进入claim_next，也不恢复原key。该结案仅允许随后shrink/disable/detach旧代次，不提供旧代次重新启用操作。未宣称经营成功。
5. 单一事务写Receipt并转terminal、完成outbox投递结算，保留全部原始内容与unknown历史快照。幂等键同请求读回，跨租户、身份/版本/hash漂移均拒绝。新的SQL入口安全定义者，只开放限定runtime调用；不使用临时SQL清理数据。
6. PG测试覆盖真实unknown→关闭→shrink可排空、存在目标Receipt/Run拒绝、fence缺失拒绝、跨租户拒绝、重放及并发锁保护。克隆迁移/全表指纹预演后部署主库，再正式处理21项。109过期待处理项保持，不作为此次无副作用声明。

文件计划 services/aos-api/alembic/versions/a0v_060_unaccepted_analysis_closure.py；services/aos-api/aos_api/ecommerce_unaccepted_analysis_closure.py；services/aos-api/tests/extension_runtime/test_unaccepted_analysis_closure_pg.py；scripts/a0v_unaccepted_analysis_closure_deploy.py；scripts/a0v_g_unaccepted_analysis_close.py。实施前审查锁顺序及原handler事务边界，必要时收紧，不为通过drain削弱要求。

## 实施前复核
- 使用与原Host相同的按operation_id排序dispatch组锁，再锁runtime；结案处于SERIALIZABLE事务，序列化冲突不自动重试。
- 收紧权限：SQL入口仅供aos_extension_maintainer执行，禁止aos_runtime直接结案；管理员身份在事务中复核。
- 校验不可变ProductEventOrigin及hash，限定原事件分析初始化；不扩大到一般unknown动作。
- 2026-09-16 06:32 隔离PG测试先红：缺少a0v_060实现，现开始最小实现；主库保持059。

## 第一次实现与验证（2026-09-16）
新增a0v_060及受限结案服务；仅当前管理员通过维护身份可调用。原事件origin/hash、同代次fence完整dispatch快照、同runtime revision、禁用binding、无running invocation、过期unknown、目标Receipt和确定性Run双重缺席均在SERIALIZABLE事务中复核。原unknown快照进入独立不可变Receipt；occurrence取消与attempt closed_unaccepted不写假accepted Receipt。新增终态触发器拒绝伪造终态或重新打开，原109pending保持。

隔离PG回归56 passed（结案、原event-dispatch生命周期、原occurrence）；请求契约另8 passed。锁竞争用真实PG行锁验证阻塞拒绝；存在目标Receipt、trigger Run或确定性Run均拒绝。克隆恢复到a0v_059后迁移a0v_060完成，全既有表行指纹未变、新Receipt表为空。主库仍a0v_059，仍21unknown/109pending，Case Run=0。

后续：提交代码与证据后，正式迁移主库、经服务关闭21项并逐项回读；审查原shrink失败意图与无Receipt证明，再恢复同一exact shrink。完成G退休后才切换诊断Host。此证据不代表真实经营首链完成。
