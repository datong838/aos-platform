# 原件调查与后继实施约束

纯检查已运行，禁止数据库连接。三份v3描述分别改变identityId、intentRef、jointReceiptRef，完整canonical hash均变化，原SQL风险入口可见的parents/申请/cases/Source参数投影不变。旧v1/v2 parser继续拒v3。原SQL风险行无完整manifestHash/identity/Intent/joint字段；旧Model证书签名只接受v1，原Target签名只接受v2。结论是完整v3持久认证未绑定的RED，不是修改后的计划获原Owner或实际COMMIT批准；没有重发native实验。

## 下一文件级方案（原atomic/typed Tasks）
首先在 `services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py` 设计独立closed的完整v3描述绑定行及显式隔离安装artifact，关联原prepared_plan_risk、完整canonical bytes/hash与相同origin xid/pid；旧风险表/旧producer签名不改。在 `aip_physical_capacity_occupation.py` 将原桥接返回的完整原风险与该描述原件绑定；`aip_physical_capacity_occupation_contracts.py` 增加独立prepared描述契约。该记录仅固定本caller所提交的整份描述，不能使identity、Intent、joint client引用自动成为权威。

复用immutable/no-truncate/RLS、sameorigin与唯一planId replay冲突，保留deferred实际COMMIT拒绝，禁止runtime直接DML。若新SQL入口允许runtime调用，必须自行核完整原Source/双父原facts/完整case与canonical body，不能信任“Python已经核过”；没有可信identity/Intent/joint producer时仍标明描述未认证、executionAllowed=false。不新建实际调用/签名/准入权限，不写已发布迁移或正式库。

RED与native必须覆盖：同plan原描述精确replay、同plan三种字段漂移冲突、跨caller/origin/tenant错配、原完整cases/parents/Source漂移、直接DML/修改/删除/truncate、提前finalize及真实COMMIT拒绝；独立只读回读原件hash/origin且回滚后0。测试只向新目录写，collection实际模块保护及事前byte备份覆盖所有可写实验路径。旧两个受损摘要不作基线历史证据。

之后才设计新v3签名域、可信issuer/身份撤回与最终joint原件消费。签名hash相等、描述落库、测试成功皆不能替代current authority/actual token/WAL deadline。此文为实施前约束；当前尚未编码以上后继产品改动。
