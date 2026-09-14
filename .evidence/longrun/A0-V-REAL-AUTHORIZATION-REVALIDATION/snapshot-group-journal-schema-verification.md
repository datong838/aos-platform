# SC4-5f4a 快照组日志结构

2026-09-14，基线f764a4bf；Lease A0-V-SC4-SNAPSHOT-GROUP-JOURNAL-SCHEMA。

新增a0v_045（父a0v_044），三张不可变表与TG_TABLE_SCHEMA限定的延迟验证函数。group member FK原source claim且run不可归两组；提交时成员数量/连续序号/actor匹配。输入manifest严格四字段/成员唯一且精确匹配本组原Ingress envelope_hash；rowCount只允许0..999完整读取范围。RLS FORCE，runtime仅SELECT/INSERT；历史UPDATE/DELETE/TRUNCATE拒绝。

先缺迁移文件7个setup错误；实现后7通过；补充输入形状和表owner不可变、原单表Ingress回归后25 passed/7既有警告/7.95s。隔离fixture使用真实原认领和输入行验证结构，不证明组业务执行器已接通。AR2 1911/187/93五数组空；memory validate和diff-check通过。

只在隔离测试环境执行迁移，主库仍此前a0v_038。无主迁移/源读取/主对象写入。应用Owner还必须完成request与manifest canonical hash、同组当前权限、全部新claim原子创建及一次读取，不能单凭三表存在当作授权或Fulfillment。

SC4-5f4a：a0v_045组认领/成员/输入不可变表与延迟完整性约束完成，25项隔离PG/原Ingress回归通过。拒绝缺成员、重复归组、错actor/hash、异常输入manifest、跨租户及历史改写；主库未执行迁移。下一应用Owner原子组认领与重放，再同事务输入保存/正式补齐。
