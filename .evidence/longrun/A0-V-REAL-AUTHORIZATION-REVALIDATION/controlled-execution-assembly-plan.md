# 受控快照执行装配方案

2026-09-12，基线 3ddcbf8b。承接领域包真实可配置、可禁入、可恢复的产品目标；当前仅组件完成，不能据此宣称经营闭环。m1 主 A0-V Lease 单写者，无 push，无主库 DDL，无源调用。

第一切片：services/aos-api/aos_api/ec_ingress_dataset.py 的 finalize_saved_dataset 增加可选 deadline/cancel_event，进入事务前和提交前检查；提交前再次 _bound_parent，借助 ControlledIngressJournal 检查当前权限及期限。旧调用兼容，普通 journal 仍验证运行与来源绑定。隔离 PG 测试 services/aos-api/tests/aip/test_a0v_ingress_journal_pg.py 在真实 dataset INSERT 后模拟权限撤销/取消，要求 dataset、history、receipt 全回滚且缓存未发布；恢复正常后原测试路径继续。不是在提交后报告失败。

第二切片拟新增 pipeline_controlled_executor.py：独立运行身份连接，严格租户事务，固定 ControlledSnapshotIngress 与 ControlledIngressJournal。准备输入正常提交后先查完成 Receipt；历史完成直接返回；否则依次恢复原 authoritative stages、project_saved_batch、finalize_saved_dataset。复用同一 scope/run/control/actor，零任意 key 或请求回调入口，不创建调度/批准，不自行换 run。每次异常向上交给既有恢复机制，未知源结果不重读。正常返回证明 dataset Receipt，不等同调度器已标成功或业务 Case 已触发。

后续接入调度路径前需验证真实 role 权限、批准续期恢复协议，以及 a0v_024 主库迁移的独立备份恢复验证。不得通过测试身份或超级用户绕过正式执行权限。

权限复核修正：最初直接检查 session_user 得到 false，不能据此要求新增 GRANT。按 apply_asset_transaction_scope 的正式流程 SET LOCAL ROLE aos_runtime 后，projection_outbox、obj_instance、graph_edge、meta_object_type、meta_dataset/history 所需表权限均 true。证据 controlled-execution-runtime-privileges.json；只读事务，未改变授权。新 pipeline_controlled_source_claim 仍不存在，等待 a0v_024 迁移。

装配实现具体文件：services/aos-api/aos_api/pipeline_controlled_executor.py；测试 services/aos-api/tests/extension_runtime/test_controlled_executor_pg.py 复用实际 PG claim/input fixture，验证下游失败后原 run 重放不再次读取源、已完成跳过所有写阶段、未知源结果不触发后续阶段。下游阶段 fixture 替身须明确标注，不能冒充完整真实权限/Receipt 集成。随后另建完整真实 Owner 集成验收。
