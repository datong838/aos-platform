# Installed分析命令端口验证

基线4c940d2a。固定solution.ecommerce.growth与analysis_advance，单次调用，不直接导入包业务；Host既有START严格解析和哈希验证，返回字段逐一对照原输入。调用前后包身份检查，隔离输入输出副本。

Red缺失模块；Green43项（新端口14、新命令9、恢复协议20）。端口Invoker是明确测试替身，不视为真实OCI；错包/类型/请求在调用前拒绝，错Case/key/time即使重算hash仍拒绝，超时只一次。AR2-7 1885/169/93无错误。diff --check通过。

未部署、未创建Run、未push。下一波原始已消费事件的精确回读：现有CandidateReader排除已生成Occurrence事件，不能直接用作分析来源复核，需同一原批次proof/当前SourceOwner下回读指定source_event_id，再接分析事务。
