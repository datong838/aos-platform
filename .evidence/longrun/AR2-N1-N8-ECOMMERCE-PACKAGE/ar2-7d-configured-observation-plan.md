# AR2-7D D1 配置修订与读取观察绑定施工卡

基线f20664a1，AOS-000571及同一Task/Lease；复习231-6 D1数据履约/质量与D2-D4退出要求。此次仅配置输入绑定，不宣布履约或源快照就绪。

## 文件与合同

1. 修改source_configuration_revision.py：新增私密连接输入封装（props不参与repr、不持久化）；通过HostTransaction单条SELECT从public.meta_source同时获取props与指向的权威历史，验证完整历史后返回。这避免两次SELECT之间配置变化导致新props/旧ref拼接。只返回输入版本，不声称历史可恢复秘密。
2. 修改ec_source_adapter.py：保留旧fetch_source_rows_observed入口和v1值。抽出私有固定规格读取体，新增fetch_source_rows_configured_observed入口接受HostTransaction和exact预期配置ref；先校验固定节点/tenant/spec，再查询当前props/ref并与预期完全相等，之后才构造连接及读取。私有配置加载函数不得由HTTP/包命令提供。旧路径继续原查询，不隐式升级。
3. 新增configured_source_observation.py：不可变独立envelope schema aos.configured-source-observation/v1，包含完整v1观察与配置exact ref，configurationIdentityOnly=true、secretMaterialVersionKnown=false、connectionIdentityVerified=false。保留v1 sourceConfigurationRef=None，不改既有Evidence内容地址；新的组合证据持久化作为下个切片。
4. 新增test_configured_source_observation.py，补source_configuration测试：真实SQL读取props/修订的一致性与秘密不进入repr，stale预期ref在连接前失败，成功观察包含同配置ref，错scope/缺配置拒绝、失败读取无结果、rows漂移及冻结；旧源观察回归。

## 限制

单条SQL验证当前配置输入不证明连接池/秘密材料或上游快照；这三项明确未知，不给质量门、业务事实或履约增加覆盖。仅18434隔离PG和connector test double，不读真实源，无新迁移、无发布、无push。下一切片才保存组合证据，并继续DataFulfill所需规范对象绑定。

## 复核补充

组合观察tenant/sourceId须与配置历史一致；“当前”仅指本次SQL的事务快照。预期ref验证早于runtime构造。props不进入repr、异常文本或Pydantic验证详情；组合及嵌套对象冻结；独立组合持久化前不声称旧Evidence已带配置绑定。
