# 受控执行真实持久层集成结果

2026-09-12，d1653e4c，m1主A0-V Lease。新增 test_controlled_executor_integration_pg.py 在独立18432随机schema，真实运行 SourceSelection/Control/claim/journal/ConsistencyStore/projector/Dataset Owner。外部源和包资产核验明确为fixture，输入fixture-shop；实际运行连接为aos_runtime，强制租户RLS，投影采用现有ownership触发器。

两种场景：正常完整完成；对象已投影后数据集Receipt CHECK故障，再重试。均读源一次；重放claim、原输入、派生记录、base Receipt、outbox、对象、Dataset Receipt、Dataset/history各只有1条，cache build也只有1条。负租户读取九张表均零行。源输入是测试数据，未调用商城；无真实业务经营Case。

初次夹具导入依赖失败，改为直接引用正式dataset迁移定义；随后夹具缺projection_input_revision_seq导致2失败，补齐测试schema的正式必需序列后2通过。该两次是测试环境修正，不是产品RED。再执行本测试、source claim owner、controlled projection合计30 passed；git diff --check及ar2-7（1804/158/93，五类错误空）通过。没有为测试修改产品代码。

连续性15:40:33Z：新安装afd792de-e85e-4680-86d0-c83404824fb3运行4744秒、76次续租、3容器running、binding ready/enabled、canary安装0。主库仍a0v_023/P01未启动。下一波a0v_024备份恢复演练与精确部署，之后正式执行入口及批准续期恢复。
