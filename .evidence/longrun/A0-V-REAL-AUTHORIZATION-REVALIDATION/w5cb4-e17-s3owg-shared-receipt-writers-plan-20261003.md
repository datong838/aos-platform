# W5CB4 E17-s3o-w-g｜共享 Receipt 全写者与受限原路径

基线 `aos-platform/m1@bdeaf233`、Authority `AOS-001215`。复习 231-3/4/5/9、栖月汇经营方案、s3o-w-d/e/f 与 D-wave 职责 Plan 发行清单。当前库只读、Host/worker/Provider关、首链未完成。

先做文件级只读清单：`aip_production_contract_store.py` 中 `_receipt` 的固定/动态 operation、`aip_content_draft_store.py` 的直接共享 Receipt INSERT、`aip_responsibility_assignment_store.py` 的 successor Plan head/revision 直写，核原 `w2_001/w2_002` 迁移的 ACL/RLS/唯一键与三种原 Store 前置来源。记录 operation→写者→结果资源/事务边界；不能把共享 Receipt 简化为只含六种 Plan operation，也不能让 successor 绕过 Plan issuer。

之后在独立 `aos-ar1c-pg:18432` 的原表形状下，先 RED 复现原宽权限/受限登录失配，再以最小独立 issuer/operation 门验证 generic/BI create/revise/freeze、successor 与内容注册的合法路径和跨写者/跨租户拒绝；保持幂等重放、CAS、失败回滚及同键锁。缺真实前置来源时只证明安全拒绝，不用 mock 或 `lambda True` 冒充正式正向。专项和相邻测试、方案/代码复审、verification、精确提交及 AOS/Prime/D-wave 收口后，再为正式迁移单独立波；不得写当前权威库。

已做第一轮只读入口盘点（非验收结论）：Python AST 回读 `_receipt` 33 个调用点，其中30固定/3动态；动态 Plan 现只准 generic/BI create/revise/freeze 六种 operation；内容草稿另有直接 `content_draft.register` INSERT，因此原应用层合法 operation 候选共37种。`rg -l 'INSERT INTO ...aip_production_contract_receipt'` 在服务代码仅定位生产合同 Store 与内容草稿 Store 两处写入站点。successor 在 `aip_responsibility_assignment_store.py` 直写 Plan head/revision 和自己的 successor 表、同事务 commit，**不**写共享 Receipt；不能把它错误归为共享 Receipt 第三写者，但 Plan 独立 issuer 必须覆盖它。`w2_001` 的 Receipt 唯一键是 `(org_id,project_id,operation,idempotency_key)`，原迁移只撤销 runtime UPDATE；`w2_002` Plan head 可变、revision append-only。后续需逐项校验调用者及迁移后 ACL 现状，不能只凭 AST 数量上正式 allowlist。

本轮隔离最小切片文件：仅扩展 `services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py`。在原 `w2_001/w2_002` 表形状的临时 schema 增第三个非 owner、NOINHERIT 的 ProductionContract issuer 测试登录，三类 issuer 分别只允许静态37项中的各自 operation；原 Store 的30个固定字面量与测试名单做 AST 双向覆盖检查。先 RED 证明当前 Plan/Content-only trigger 拒绝原 `eval_contract.create`；然后最小修测试 SQL 协议，验证全部37项的合法/越界、runtime 直写、未知操作和跨租户拒绝，保留 Plan 同键锁与内容正向。此为迁移设计实验，不将测试 SQL 当正式 migration 或生产凭据；后续原 Store 受限连接及回滚/CAS 仍另测。
