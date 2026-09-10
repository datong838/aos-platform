# L3来源数据库组合验证方案

基线34f0cfe3；复用隔离PG fixture，在随机schema克隆现有public六张Evidence/Disclosure/Receipt表的结构，合成Evidence，不改public数据。测试真实resolve持久化→新连接正文读取→原请求task换绑拒绝→直接撤销后拒绝→负租户不可读。为克隆表显式配置tenant RLS，区分测试权限与生产权限，不宣称生产grant已验证。

文件services/aos-api/tests/aip/test_a0v_disclosed_source_pg.py。不使用mock Store/policy，校验真实SQL/DTO/Receipt组合。执行后只清理fixture自己的schema。没有Provider调用或首链完成结论；真实字段导航和运行装配继续后续推进。
