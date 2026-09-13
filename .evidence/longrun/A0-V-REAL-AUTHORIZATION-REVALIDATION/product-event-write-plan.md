# BG-02 事件策略原子存储片

基线c47ae4e9，租约A0V-PRODUCT-EVENT-WRITE-20260914。新增040迁移及隔离PG专项。新事件专用函数复用现有三表、Case head/revision，不替换旧定时函数。输入完整包事件策略、下一Case、期望两版本、原key与组合hash；所有JSON关键校验用IS DISTINCT FROM/IS NOT TRUE，拒绝缺字段与NULL。

事件schema/字段集合、精确ref用途、整数/UTC时间/范围、tenant、策略hash及Case hash验证；按Case→policy锁顺序读取当前事实，要求当前Case ACTIVE，methodRef与当前Profile一致，policy caseRef为原版本，下一Case仅改七个调度审计字段。首版无旧绑定，后继只接受同事件类型、连续prior及Case现有精确指针；时间不能倒退。用组合hash核对同key重放，先验证输入后锁并回读Receipt；拒绝冲突，不重复写。

同事务插入策略history/head、Case后继/head和原command Receipt。事件enabled恒false，不创建ScheduleBinding、Occurrence或审批。SECURITY DEFINER固定search_path，PUBLIC不可执行，仅runtime获得函数EXEC，原表写权限不扩大。数据库校验是持久化边界，不替代Host当前来源/方法/批准复核。

测试使用独立aos_test_*_ti4_test数据库，完整迁移链。合法同事务写入、同key回读、hash/tenant/ref/业务内容漂移、外层回滚、旧Case CAS、双版本联动、直接表写拒绝，且未启用。主库保持038，禁止自动部署新head。
