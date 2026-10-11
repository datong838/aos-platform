# 剩余全目录列ACL扫描调查与等价优化候选

Rules231、原完整Source/准入合同、catalog实施方案；1786强投影CURRENT，原Task同owner有效且唯一Lease，无Delivery。候选一FACT剩余扫描成本（已登记）；候选二完整native结束与正式来源（依赖原Root证明）。选一，先只读查询对比。

本目录保存固定A/B/A/B查询和结果。两条全目录列ACL检查当前依赖LATERAL aclexplode(x.attacl)过滤NULL，拟仅显式x.attacl IS NOT NULL让规划器先筛ACL，完整UPDATE/其他权限/grant option/允许锁列五个计数均保留。不限制schema或relkind，不丢掉其他schema越权，不缓存或去掉任何调用。原默认ACL/角色/表/策略/trigger/锁后当前性不变。

仅若同原独立库只读结果相同且实际成本下降才实施：产品services/aos-api/aos_api/aip_provider_capacity_catalog_audit_profile.py，测试services/aos-api/tests/aip/test_provider_capacity_catalog_audit_profile_pg.py。两处固定片段精确匹配，不重写原发布store或迁移；新完整家族digest随编译绑定。原列ACL等价矩阵扩展全目录count与非法ACL检测、其他schema/owner/PUBLIC/撤销覆盖；原身份和Main相邻复测。全Source新鲜一次试验不得重放旧失败，不改变TTL/业务权限。若A/B无收益只留调查，不改代码。
