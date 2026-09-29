# W5CB4 BG-00aj｜同事务 Eval writer 当前 authority 预检方案

## 上位复习与本波收窄

228 G2.2/231、BG-00v/w/ab/af/ah/ai 已分别具备纯双签名判定、持久读取/Report 消费、默认关闭独立身份，以及 test-only 最小 SQL 权限/原子性。写入前必须在**同一 serializable writer 事务**读取当前 issuer root、Target/Judge identity、截至 cutoff 撤销与 Owner/approval，并将其与呈交证书/Receipt、Report case 和独立 input hash 精确核对；若先在另一个事务预检再写会有撤销竞争。BG-00ai 已证明 DB FK 不验 Ed25519。本波先实现这个缺口，后继 BG-00ak 再组合 INSERT；当前没有正式 G2 issuer/Owner，不接生产 Host/runner。

## 文件级计划

1. 新增 `services/aos-api/aos_api/aip_eval_writer_authority_preflight.py`：只接受调用方已开启的 serializable/精确 tenant、`current_user=aos_aip_eval_writer` 的同一连接；传入 immutable Report、每 case 独立预期 input hash 和双证书/Receipt。精确 SELECT root/identity/revocation；核公钥 hash、证书 JSON/hash、Owner/approval/source、时间/租户、独立 Target/Judge；调用既有 `verify_execution_pair` 逐 case 验签及结果与 Report，返回已验证的 case proof 集合。不得读持久 Receipt（此时尚未写入）、不得写任何表/注册路由或放宽 ACL。缺 root/identity、错签、撤销、缺 case、跨租户/错 role/isolation 一律拒绝。
2. 新增 `services/aos-api/tests/aip/test_aip_eval_writer_authority_preflight.py`：test-only a0v114 回滚事务、BG-00ah 专属角色和 BG-00ai 临时 SELECT policy；先 RED，再用 test-only Ed25519 真签名正向，缺 authority/撤销/签名漂移/错误 role 与隔离级别负向。测试后授权/policy/authority 行全回滚，当前库仍空。
3. 专项/相邻累计，复审这一步只证明“写前预检”，不宣称同事务写入成功。BG-00ak 才把它与 BG-00ah 独立 connector 和 BG-00ai INSERT 包装在一个事务，故意 Report 失败全回滚。当前正式 issuer/Owner/批准、G2 内容/S3 仍需外部真来源。
