# W5CB4 BG-00af｜Skill Eval Report 全 case proof 只读消费验证

## 范围与实际修正

在 `w5cb4-bg00af-skill-eval-report-proof-consumer-plan-20260929.md` 后，新增 `services/aos-api/aos_api/aip_eval_report_proof_reader.py` 及对应隔离 PG 测试。曾预期本波也实现同事务写入；复核 BG-00z ACL 发现四张正式 issuer/identity/Receipt 表对 `aos_runtime` 只有 SELECT，未有合法正式 issuer/Owner 与专属写入权威。故只实现可独立验证的 read-only consumer，不改 ACL、不解除 Skill runner 的 `formal Skill Eval executor authority unavailable` 禁入。

## 机制与验证

- consumer 只使用调用方同一 repeatable-read/serializable、精确租户 runtime 事务；回读 succeeded Run 的 suite/target/dataset/judge、完整不可变 Report/hash、sidecar 全 case 集合。逐 case 调 BG-00ab 持久 reader 验 root/identity/撤销/双签名/Receipt，再与 Report 的 actual/expected/pass/detail 和 sidecar 双 ID/claim hash/时间逐项核对。无路由、Host 或 Gate 接线，无数据库写入。
- 先在 test-only `aos_bg00ad_schema_v2_20260929@a0v_114` 运行未实现函数测试，pytest collection 退出 2（缺模块）；新增最小代码后专项 `3 passed`。新增当前撤销、Report 漂移、缺 input 与双 case 缺一条 sidecar 的负向；专项 `7 passed`，退出 0。最终专项+相邻签名/sidecar/持久 reader/预览门 `35 passed`，退出 0。
- 测试仅在 `org-org/dev-project` 隔离回滚事务放 test-only 密钥/Run/Report/sidecar；`dev-org` 只作只读 GUC canary。测试后 clone 的 issuer/identity/revocation/Receipt/sidecar/Report 六表均 0；当前库只读复核 `aos_current_preview_20260927@a0v_114` 五张新 authority/sidecar 表均 0。代码 `compileall -q` 与 diff check 退出 0。

## 边界与下波

这证明隔离只读消费者的失败封闭，不是合法签发、真实 G2 内容、S3 或经营链验收。Report proof 未接生产 Gate；同事务 writer 的 DB role/Owner/批准尚无正式来源。下一波 BG-00ag 先审 `aos_runtime`、`aos_app` 与可用 transaction owner/SECURITY DEFINER 边界，设计最小不可越权 writer；不得直接授四表 INSERT，也不以测试密钥/表行充当正式 authority。当前 PG/API/Web a0v114 维持，Host/worker/Provider 关闭。
