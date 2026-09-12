# 受控执行装配及提交前当前性验证

2026-09-12，基线 3ddcbf8b，主 A0-V Lease，m1 单写者。

ControlledSnapshotExecutor 固定原 scope/run/control/actor，准备输入提交后查已完成数据集 Receipt，再按原输入恢复 authoritative stages、本批投影、数据集完成。正常返回是数据集完成证据，不标调度成功、不创建新授权、不发起自然业务 Case。

finalize_saved_dataset 新增可选 deadline/cancel_event，入口及提交前检查，提交前再次绑定当前 journal。真实 PG 数据集写入后撤权/取消均使 dataset/history/receipt 回滚且缓存为空。旧入口保持兼容。

RED：缺少 cancel_event 参数导致两个后端用例失败；缺少新装配模块导致 4 项失败。实现后五个文件合计 40 passed（controlled executor、snapshot ingress、projection、a0v ingress journal、旧 durable executor）。后端 journal/store 测试含真实 PostgreSQL；装配路由测试下游阶段为显式替身，不能声称完整集成完成。

角色检查修正：直连 session_user 没有直接表权限，正式 apply_asset_transaction_scope 后采用 aos_runtime，所查表权限齐全。未新增 GRANT。证据 controlled-execution-runtime-privileges.json；其权限检查只证明表授权，不证明全链所有 RLS、触发器及真实批准均已验证。

主库 pipeline_controlled_source_claim 尚不存在，a0v_024 未部署，P01 未启动，未调用真实源库。清册 1804/158/93，五类错误数组为空，git diff --check 通过。下一波次完整隔离 PG owner/Receipt/投影/Dataset 集成，然后准备主库迁移和正式执行路径。
