# 有界表发现验证

基线380ab0cb。新增list_configured_tables绑定self.database，只读事务中查询information_schema.tables名称/类型，最多返回500并明确truncated。无业务行、无表注释/行数，不枚举其他schema。既有通用发现方法不改。

专项先3 failed（缺方法）；实现后3专项+28既有Jdbc测试共31 passed，git diff --check通过。模拟0/2/501条结果验证绑定、边界、事务调用和输出字段；未做真实MySQL/SSH或错误传播专项，真实探针仍须配置版本校验及reuse_cache=False。旧7启动警告/JDBC退出日志问题保留。

本增量是端到端C/D的底层方法，不是HTTP探针或向导完成。向导仍有mock表清单，下一步probe service和接口装配后必须替换。无真实数据/模型调用，无push，230 L0挂起。
