# W5CB4 E17-s3o-w-f｜职责 Plan 创建 operation 白名单

日期：2026-10-03。已复习 231-3/4/5/9、栖月汇经营方案、s3o-w-d/e RED 与隔离发行协议。只读 AST 盘点：`aip_production_contract_store.py` 的 `_receipt` 共33个调用点，其中30个固定 operation，3个 Plan 调用传动态 `operation`；另外 `aip_content_draft_store.py` 直接写同一 Receipt。`revise_responsibility_plan_in_transaction` 与 `freeze_responsibility_plan_in_transaction` 已只接受 generic/BI 两种 operation，`create_responsibility_plan_in_transaction` 仅特判 BI 而没有拒绝其它值。调用者为原 generic wrapper 和正式 BI preparation。

## 文件级最小修复

1. `services/aos-api/tests/test_w2b_production_contract_store.py`：先在隔离 PG 加真实事务负例，传非 Plan operation（例如 `content_draft.register`）调用原 create in-transaction，断言**在依赖读取前**以 `ProductionContractConflict` 精确失败且 Plan head 零新增。用已验证的 `CreateResponsibilityPlanRequest`，不使用 `lambda True` 或虚假来源申报业务完成。当前 RED 若落到模板缺失，只能证明错误 operation 已越过入口，不能声称产生了伪 Receipt；修后应转为精确入口拒绝。
2. `services/aos-api/aos_api/aip_production_contract_store.py`：只在 create in-transaction 入口增加与 revise/freeze 对称的精确 operation 白名单 `responsibility_plan.create` / `bi_responsibility_plan.prepare`，非法值在读取依赖和任何 SQL 前失败关闭。不改公开 API/BI 合法路径、hash、Receipt、CAS。
3. 专项与相邻原 Plan/BI 回归，复审方案/代码一致性，verification 与上下文收口。当前库不迁不切、Host/worker/Provider 继续关闭；白名单只收紧应用层合同，不替代数据库独立 issuer/ACL/trigger。
4. 因涉及当前 API 运行逻辑，在代码精确提交、签名预检/备份/迁移与卷身份回读后，按既有本机预览控制面完整 PG→API→Web 重启，浏览器复核原禁入页面并只读回读关键计数。仅以当日最新代码和原权威卷报告本机质量门；不因重启开启 Host 或声称首链。
