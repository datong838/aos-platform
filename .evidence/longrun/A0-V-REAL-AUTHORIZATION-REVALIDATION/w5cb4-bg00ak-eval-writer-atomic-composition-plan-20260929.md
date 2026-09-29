# W5CB4 BG-00ak｜隔离 Eval writer 签名证据原子登记方案

## 上位方案与边界

按 228 G2.2/231、BG-00ab/af/ah/ai/aj 和当前 Skill guard，正式双签名证据须在当前 issuer/Owner/撤销快照下判定，Receipt/Report/sidecar 同笔提交。BG-00aj 只读预检已经要求专属 writer + serializable + 精确租户；BG-00ai 已证明 test-only 最小 SQL ACL/FK/失败回滚。当前库没有正式 issuer/Owner/ACL/G2/S3，故本波只实现默认关闭的组合器并在 test-only PG 验证，不解除 Skill guard 或接 Host/Gate/路由。

## 文件级计划与 RED

1. 新增 `services/aos-api/aos_api/aip_eval_writer_atomic.py`：公开入口只用 BG-00ah `configured_eval_writer_connection`，必须显式 expected database，配置缺失立即拒绝；在同一新 serializable 事务 SET LOCAL 专属 role/租户，从数据库 `transaction_timestamp()` 锚定当前撤销 cutoff，再调用 BG-00aj preflight，逐 case INSERT Target/Judge Receipt、单 Report、每 case sidecar。复合 FK 与不可变字段保留；无 UPDATE/UPSERT/自动 retry。重复或未知结果只失败，让调用方只读对账。提交后不自动提升 Gate。
2. 新增 `services/aos-api/tests/aip/test_aip_eval_writer_atomic.py`：先 RED。test-only a0v114，用真实 Ed25519 已签 test-only 凭据、专属 LOGIN 与临时最小 ACL/RLS；正向独立连接提交后核三类行、故意 Report 冲突整笔回滚、错签拒绝零新行、缺配置拒绝。为避免连接间不可见，test-only seed/ACL 必须显式提交，finally 在单个 test-only 事务短暂禁用 append-only 用户触发器精确清理并恢复，独立连接确认行/触发器/策略/临时 LOGIN 均归零；绝不当前库。
3. 微调 `services/aos-api/aos_api/aip_eval_writer_authority_preflight.py` 与对应专项测试：封闭 Report 计数/通过率与 case 不一致的漏洞。`services/aos-api/tests/aip/test_aip_eval_execution_authority.py` 的签名 fixture 增加可选当前时间，不影响默认历史用例；真实 connector 测试必须用数据库当前 cutoff，不能注入旧时间。
4. 专项及相邻累计、代码/方案复审、verification 落盘，精确 m1 commit；更新 authority/01/06、312 与 D-wave。正式 ACL/凭据/issuer 的开通需独立安全切换波与真实批准，不在本波。
