# UQ6-A 读取账本部署执行器准备

2026-09-13，基线d7c56562，m1；租约A0V-UI-READ-LOCAL-DEPLOYMENT-20260913-V2。项目强一致投影CURRENT，parent authority AOS-000573未改变。

新增固定030→035部署执行器：仓外私有备份、新建拒绝PUBLIC CONNECT的恢复副本、前后业务表指纹、精确迁移链/锁/DDL超时、空队列FORCE RLS/精确11列UPDATE/API无表权限/5函数ACL核验。dump/migrations/executor哈希绑定证明；不可覆盖的0600/fsync执行意图先于主库DDL，未知结果不重跑，只读回核验。原Host不重启。

独立完整迁移测试库验证12 passed，7项既有警告。实际验证了正常schema、INSERT/身份列UPDATE权限扩大拒绝、备份/版本/执行器/迁移/数据证明漂移拒绝、已有意图不重试及私有不可覆盖写入。

当前只是执行器准备；实际主库仍030，下一步真实备份恢复并升级副本，通过后才执行主库增量迁移。没有业务写入或发布授权替代。
