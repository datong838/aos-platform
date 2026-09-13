# UQ2-D 应用受限入口贯穿验证

2026-09-13，基线4952795e。新增ui_read_api_database.py，RuntimeUiReadAdmission切换到public限定的两个固定函数。作用域与事务预检、remote OpenFGA不降级、受限主体事实、固定请求入队、摘要及回执合同校验均在现有调用事务内；没有直接成员表行锁或请求表DML。

28 passed：13项应用门禁 +15项角色/函数真实隔离PG测试。应用门禁也改用非超级LOGIN+SET ROLE aos_ui_read_api；目录仍是用于隔离门禁顺序的输出替身，真实签名制品尚未新增。测试连接仅将public函数名重定位到临时schema，不模拟数据库权限。撤权、旧资源、错scope、角色/markings不足、command-only、重复模块仍拒绝。AR2扫描1842模块、163分类、93迁移，错误集合为空；diff检查通过。

UQ2入队接入代码已串接，HTTP尚未开放。主库a0v_030和原宿主不变。下一波UQ3：固定只读请求领取/封存，现有signed_read Attempt、当前主体/签名目标再校验、同一快照与原PreparedJob调用、未知结果不重放与关闭排空。运行包尚无固定读取注册，须后继签名版本交付；不能将入队成功视为业务链完成。
