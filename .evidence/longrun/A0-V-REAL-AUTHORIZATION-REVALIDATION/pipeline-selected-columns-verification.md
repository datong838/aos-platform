# 源端字段投影验证

2026-09-12，基线ad51c4b6。JdbcConnectorRuntime.read_rows新增尾部可选columns参数；指定列时在源SQL生成明确投影，不查询星号，严格限制1..1000行。列清单仅允许1..100个唯一普通标识符。省略columns时保持旧接口行为；未擅自改图或赋予运行权限。

RED：21项新增测试因不支持columns参数失败。GREEN：新字段投影、既有JDBC运行时、独占源连接、EC JDBC源适配器共75 passed，3.68秒，7项既有警告。包含SELECT精确列名、店铺参数与游标参数组合、无效标识符/重复/空列/超过100列、None/bool/浮点/越界limit在任何DB调用前拒绝、异常只读事务回滚且不重试。fake连接仅证明构造和控制流，不冒充真实源库执行成功。

AR2 ar2-7检查1791/158/93，五类错误均空。git diff --check通过。未改迁移、未添加HTTP入口、未修改既有PII清洗或改变默认全列行为。本波不宣称旧数据读取已遵守PII不出库，也不宣称全量数据已同步。

下一步：从已安装且固定hash的包映射、Schema和脱敏资产解析选列，与当前SourceSelection权限及版本绑定，再让受控P01读取使用该方法。来源选择Owner、持久控制、SourceAdapter正式接线、真实ScheduleRun/Receipt尚未完成。m1串行、不push、230 L0挂起。
