# D01原产物接收与恢复

2026-09-11，基线cb0e30a4，AOS-000573。内部接收器，无HTTP/Provider调用，不单独成为业务质量放行入口。

新增 `services/aos-api/aos_api/ecommerce_analyst_portrait_receiver.py`；复用D02模式：attempt稳定advisory事务锁，同scope成功attempt及D01 Run/route/policy、原Artifact所属TaskRun/AgentRun/attempt、当前原文访问与hash；首次保存读取统一D01输入、纯转换、正式Owner publish_insight(expected0)，调用方事务负责提交。已保存重放只返回历史Insight，仍检查原文访问/原产物/actor/method/eval/cutoff，不重做披露授权，也不授权下一步；空metric_sources仅在历史恢复路径允许。

修改 `ecommerce_analyst_authority_store.py`，补get_insight_exact和find_insight_publication_receipt，检查scope/identity/revision/实际payloadhash，沿用既有表，无迁移。

新增对应测试：一次保存历史恢复，未知/缺回执/错D01/原产物漂移/输入读取拒绝不发布，历史查询精确校验、跨租户、实PGOwner保存/回滚。后续执行service须独立完整治理和事实质量门禁，不能把本模块未接宿主的内部验证视为首链完成。

## 回滚验证发现与最小扩围

真实PG回滚测试发现既有Owner._publish主动conn.commit；直接bound原连接会提前提交并释放事务锁。复用既有TransactionBoundConnectFactory(HostTransaction(conn),scope)包装Owner调用，使commit为空操作、外层唯一提交。三处接收器D01/D02/D03均使用相同模式，一并最小修复；不修改Owner独立调用语义。补正式Owner外层回滚与三个Receiver使用事务包装测试，保持原文读取同原连接。
