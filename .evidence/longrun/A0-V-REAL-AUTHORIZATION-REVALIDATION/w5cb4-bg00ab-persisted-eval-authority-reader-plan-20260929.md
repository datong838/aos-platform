# W5CB4 BG-00ab｜持久 Eval authority 只读消费者文件级方案

## 上位复习与当前事实

228 G2.2 要求内容事实/渠道 Evals 与 Draft-only 负向门，231 要求当前安装真实证据。BG-00v/w 的纯 `verify_execution_pair` 已验证 Target/Judge 双独立签名、精确 run/suite/case/ref/hash、撤销与有效期；BG-00y/z 在当前 `a0v_113` 建成四张默认空、RLS/FORCE、运行角色仅 SELECT 的持久表。BG-00aa 发现当前 G2 Eval 仍是 `BLOCKED` 占位、四表空，正式 issuer/Owner/批准及 S3 缺失。因此本波只建消费机制，绝不填当前表或启动 Host。

## 文件、边界与顺序

1. 新增 `services/aos-api/aos_api/aip_eval_persisted_authority_reader.py`：接受调用方现有单一、已绑定租户的 psycopg 事务连接及期望的双 Receipt；生产调用方须用 `connect_read_only(scope)` 的 REPEATABLE READ 事务，隔离测试可在回滚事务中先造机制行。reader 只执行 SELECT。只按期望 tenant、run、case、purpose 精确查询四表；核 DB role/GUC 与 scope 一致；root 的 key/hash、Owner/approval/source，identity 的证书 JSON/hash/公钥/ref/Owner/approval，Receipt 的全部 DB 列与签名声明相等；查同租户截至 `evaluated_at` 的撤销事件；最后调用既有纯签名验证器。任一缺失、重复/漂移、时间或租户不符均抛 `EvalExecutionRejected`。返回已有 `VerifiedEvalExecutionPair`，不写表、不注册路由、不注入正式来源。
2. 新增 `services/aos-api/tests/aip/test_aip_eval_persisted_authority_reader.py`。先 RED：隔离 test-only PG 的空 authority 必拒；已签名的测试专用 issuer/Target/Judge 双 Receipt 在 rollback-only 事务内正向可读；分别改缺 root/identity/Receipt、跨租户、撤销、签名/DB 字段漂移、过期均拒。只用 `org-org/dev-project` 插入 test-only clone；`dev-org` 仅只读 RLS canary。不得使用 test mock 作为业务验收。
3. 运行专项与现有双签名/迁移相邻测试，校验 diff、代码和方案一致性；任何新增迁移或当前 DB 改动须退出本波并重新立独立安全迁移波。无浏览器入口变化，浏览器验收不适用。

收口写 verification、D-waves/303 上下文、精确 m1 提交并继续下一波。读消费者的成功仅证明隔离机制，不证明 G2 正式内容、签发/审批、真实 S3、自然首链或 Report/Gate 消费。
