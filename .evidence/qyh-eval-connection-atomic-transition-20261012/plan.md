# 原 Eval Run connection-bound CAS/event 最小实现

依据前波 qyh-signed-skill-lifecycle-contract-20261012 合同第4步。完整producer仍按原合同实现，本波只解除原转态函数内部commit阻断同事务终结的结构缺口。

修改 services/aos-api/aos_api/aip_eval_authority_store.py：新增内部 _transition_eval_run_with_connection(conn,scope,event,expected_version)，原锁行、tenant验证、版本/from状态/转换/sequence校验、event写入、CAS更新原样复用；不打开连接、不commit。原公开transition_eval_run仍在原连接上下文调用新helper后commit，异常封装不变。该内部helper不提供登录/Owner/签发授权，也不开放新的HTTP入口。真实producer调用必须原独立writer、SERIALIZABLE和完整intent/证明门，不能仅调用此helper直接宣布成功。

新增 tests/aip/test_qyh_eval_atomic_transition_pg.py：复用原Authority Store/schema fixture，在18431同一授权cluster的新pytest库新schema中准备新测试Run；canonical org-org/dev-project测试对象与dev-org canary，仅fixture非业务。验证转态后外部连接仍看旧版本，晚期失败rollback恢复Run和event，原caller commit持久，stale版本/跨租户/非法转换拒绝；同版本并发两连接只一胜。无需签名/report假数据，不授producer完成。保留当前正式库和历史65Runs、原12Runs、不做schema迁移/角色GRANT/worker启动。

RED须在未实现方法时真实AttributeError；GREEN专项与原authority store/runner相邻验证，记录skip数量。校验git22受保护文件不变；精确提交/Delivery/CAS/7strong同步。无页面/API入口变化，无浏览器完成宣称。

复审增量：内部helper显式拒绝autocommit或未声明事务的连接，避免event与CAS逐语句提交。旧公开接口保留标准事务连接路径；原自动提交连接的非原子调用现在明确拒绝。新增真实服务端UniqueViolation晚期失败回滚和autocommit RED。此边界是原同事务合同必要实现，不赋予运行权限。
