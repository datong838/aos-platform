# 商品原文与候选快照不可变证据

2026-09-11，基线a01caadb，AOS-000573。用户授权串行继续。将上一波计算接到可恢复的正式Evidence；保留源数据类型、原观察hash和业务口径，不手工补业务数据。

## 文件与实现

- `source_read_observation.py` / `ec_source_adapter.py`：把既有两类公开字段清册集中到Observation契约，Connector行为不变，归档同清册拒绝额外字段。
- 新 `source_observation_rows_codec.py`：复用原_typed编码算法；严格有限类型逆变换，支持原Decimal/float/datetime/null/int/bool/string/list/dict，深度和UTF8总大小限制；往返必须保持observed_rows_hash，不作数字/日期猜测或截断。
- 新 `ecommerce_product_content_evidence.py`：显式HostTransaction/scope内部Owner。put先验证完整配置观察/当前shop/原文hash/共用质量规则；完整类型编码原文、选定scope引用与候选快照保存进aip_evidence。稳定ID由原观察、选择、actor、可选TaskRun和政策版本产生，不含重新计算时间；并发只保留首次快照。read_exact复核列/正文hash、上游两个Evidence（配置观察和原观察）、原文hash及冻结质量/候选计算，保留首次测量时间，禁止覆盖历史。可选TaskRun不强迫源准备先有运行任务，无默认提交。
- 新 `aip_evidence_dependencies.py` 与修改 `aip_production_contract_store.py`：只有显式generic evidencePolicyVersion启用的Evidence执行依赖存活检查；同租户/精确r1/hash/实际正文hash/未撤销，最多100个不重复叶依赖，拒绝嵌套依赖防循环。平台不依赖电商模块。该检查只收紧依赖可用性，不授予读权限或外部用途。
- 新对应codec、商品Evidence测试；共用质量/候选/QueryEvidence披露回归。

## 证据语义与权限

原始商品字段来自受信宿主的固定JDBC公开字段观察入口；内部Owner不提供HTTP任意原文写入。原文归档使用database来源语义和internal标记，沿用平台对受控数据库Evidence的披露策略；不是发布许可。上游两个只含元数据的Evidence作为撤销依赖，根Evidence的读取仍需当前正式披露/actor/marking。完整原文最多2MiB和现有100行上限；不扩大成大规模支持。候选只是内部素材准备，不生成Insight/Task或业务增长结论。

## 验证与退出

先失败测试；类型保真/非有限数/非规范标签/深度/大小/重复键拒绝；一次性PG验证幂等、不同时间重放、回滚/并发、类型保真恢复、正文/上游撤销与披露失效、跨scope、额外字段拒绝。根快照测量时间位于原观察结束与记录时间之间，读回重算不能改变它。所有实际写入仅隔离测试库；不迁移主库/调用Provider/重载API。文档、清单、哈希、精确提交后直接下一波正式业务Metric/Query与D01输入接续。不push，230 L0挂起。

实现补充：`ecommerce_product_content_snapshot.py`抽取共用纯计算函数，历史读回按首次测量时间重算，不重新解释当前Shop选择。SERIALIZABLE并发冲突由调用方重试整个未提交事务；Owner不重试外部调用。
