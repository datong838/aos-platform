# AR2-7D D1 配置绑定读取观察验证

- 基线f20664a1，AOS-000571，同一m1 Task/Lease；方案先行。本切片不新增迁移，不连接真实源。
- 单条public SQL同时读取meta_source.props及其指向的实际配置修订；私密props不进入repr或持久化。新入口在runtime构造前匹配expected配置exact ref，返回前核对tenant/sourceId；“当前”仅是该SQL快照，不声称持续有效。
- 新独立不可变ConfiguredSourceObservation组合v1观察和配置引用，嵌套引用/观察/租户冻结；旧SourceReadObservation保持sourceConfigurationRef=None，既有Evidence哈希不变。组合对象尚未持久化。
- RED：新模块缺失。首轮18项通过后增加秘密异常反例，确认旧runtime异常文本直接暴露导致失败；仅configured边界转换固定安全错误/from None，构造及读取反例均验证格式化traceback不含秘密。旧observed失败语义保留。
- 新鲜5文件回归64 passed, 9 warnings in 52.01s；包含7项组合专项、8项配置SQL/迁移专项及旧观察/持久化回归。只使用本次18434临时PostgreSQL及connector test double。无真实源或秘密访问。
- 独立只读终审无本切片剩余阻断：adapter SHA256 a91dcf9edb373b4b37a8ddc575e3e6860cc8a344e7b6bea25bede796750bf19c；envelope 9d924a784342647768cc7bb5ffdb06867eb678cba0bb86bc418a90fb3a69b9de；reader 02028186582c589456b4be21d9b2b2b289f9eef2a7022a702a8a3d97220f1693。不是外部Prime PASS。
- 尚存限制：jdbc_connector_runtime既有缓存清理日志仍记录异常文本；外层不能撤回日志。此项需在真实连接前单独治理，当前不宣称全链日志安全。配置秘密材料版本、连接身份和上游快照仍未知。
- 下一步保存组合证据并exact回读配置Owner，同时继续规范对象关联及DataFulfill；整波AR2-7D/7E未完成，无push、230 L0继续挂起。
