# Subject持久模式验证

Task AOS-SUBJECT-PERSISTENCE-20261001。用户已批准subject-review实现/隔离验证；当前库维持只读，本波a0v131只在标准临时数据库升级。
- RED：services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/aip/test_aip_eval_subject_persistence_pg.py -q，临时库head=130而要求131，1 failed/5.69s/exit1；/tmp/aos-subject-persistence-red.log。
- GREEN：标准临时数据库完整迁移至131；subject schema、原root/identity目的约束、Runtime SELECT-only ACL、RLS FORCE、追加写/截断保护和三条父FK+同信封source外键检查。subject+原签名相邻37 passed/5.70s/exit0，10既有/故意非法类型warnings，零skip；/tmp/aos-subject-persistence-green.log。
- 迁移新增subject表默认空；Runtime仅SELECT、PUBLIC零权限；根/证书purpose扩展为独立用途，但原v1 reader/writer显式只接受eval-execution，且原v1签名测试继续通过。schema从不签发身份、不创建EvalRun/Report/配置、没有消费许可。
- 源申明不可变，并由同租户Run/身份/来源收据FK锁定。当前尚无正式issuer/approval/identity签发Owner、受限写者与同事务reader；本次DDL只建立存储门。测试只查临时库schema与空态，不冒自然链正向。
- 未连真实当前库、未用Provider/Host/worker，未读取商城源、未回放旧Run、未push。历史dirty未改；无UI改动，浏览器不适用。下一波同事务reader+受限写者/正式签发Owner，需原生产来源及Report消费，不能把表存在计作业务完成。

final日志SHA256=a35e63227f93570e6ade00e1bd196e5024596bf7e04b7a6b043bee87c0a2668d
