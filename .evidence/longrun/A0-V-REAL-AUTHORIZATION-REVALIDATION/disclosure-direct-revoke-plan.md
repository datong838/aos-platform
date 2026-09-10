# EvidenceDisclosure 直接撤销检查方案

基线 c25ce359，属于真实来源正文读取的前置修复。总目标仍是231-6真实经营首链与八工作台；本项不能代表A0-V或首链完成。

现状：_evaluate_disclosure 仅检查bundle撤销，遗漏aip_evidence_revoke_event，因此已直接撤销的Evidence仍可能得到L1/L2/L3授权。复用现有Owner及现有exact撤销表，不新建权威。

改动：在当前tenant与exact evidence revision/hash下读取直接撤销事件，存在时追加EVIDENCE_REVOKED；既有决策逻辑不给grantedLevel、正文或L3 source句柄。resolve及当前策略复验共用此逻辑。文件为services/aos-api/aos_api/aip_production_contract_store.py与tests/aip/test_evidence_disclosure_direct_revoke.py。

验证先红后绿：三个披露层级的有效/撤销对照，精确SQL scope/id/revision/hash绑定；查询异常不得继续授权。使用合成数据，不访问真实数据或Provider。随后检查受影响测试和语法。

边界：本项不实现L3正文materializer，也不解决并发撤销与消费之间的事务锁；后续reader须绑定原请求/actor/有效期并在读取边界复验。无迁移、无页面改动，无现存数据修改。回滚可独立revert本项提交，但会恢复已知缺口。
