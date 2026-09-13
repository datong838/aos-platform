# 安装包分析启动命令

基线1336a602，子Lease A0V-INSTALLED-ANALYSIS-START-COMMAND-20260914。增长包已有AnalysisRuntimeRequest和命令哈希协议，但运行入口尚不接收事件启动计算。

新增 bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analysis_start_operation.py；修改同目录__init__.py，在原analysis_advance下固定kind=build_analysis_start，仅接收occurrenceRef/caseRef/profileRef/cutoffAt/idempotencyKey。严格白名单字段和exact引用、UTC秒、规范幂等键。复用AnalysisRuntimeRequest.command_payload与canonical_command_hash返回启动命令；不创建Run、不调用Host、不宣称授权。

新增 services/aos-api/tests/extension_runtime/test_ecommerce_analysis_start_operation.py，正例与Host严格解析一致、未知字段/类型/引用用途/时区/键拒绝、输入不变与重复确定性。旧注册条目和旧derive_structure_case不改。新代码未进入已签名候选，必须后续新候选评审安装，不能修改历史候选。

退出：定向与邻接回归、AR2清册、文档/commit/Receipt。后继平台installed port和当前claim/policy事务承接。
