# D02 诊断可信保存与恢复方案

日期：2026-09-11。基线：m1 `70d698d8`；权威 AOS-000573。承接 231-5/231-6 的真实业务自动链与串行施工要求。用户允许持续开发、自测；不 push，230 L0 挂起。

## 产品目的

经营参谋的诊断必须成为可追溯、可恢复的正式输入，供后续业务计划使用。只接收已经完成并保存原文的 D02 调用，不在恢复时再次请求模型。此波不是栖月汇真实首链验收，也不创建批准或运行状态。

## 实现路径与目录

- 新增 `services/aos-api/aos_api/ecommerce_analyst_diagnosis_receiver.py`：显式租户连接、原文恢复、D02 身份/原始 Artifact/调用收据检查；同事务校验当前 Insight、完整 EvidenceBundle 与有效正文披露授权，再交原 Owner 保存 DecisionSummaryRevision。
- 修改 `services/aos-api/aos_api/ecommerce_analyst_authority_store.py`：仅补 Decision exact 历史读取及对应 publication receipt 读取，验证 payload 重算哈希、租户、ID、版本。
- 新增 `services/aos-api/tests/test_ecommerce_analyst_diagnosis_receiver.py`：有效接收、重复接收、漂移拒绝、源权限失败与隔离数据库验证。

## 一致性与安全边界

1. 锁键由租户与 attemptId 计算，事务咨询锁防止两个接收者创建重复记录。保持既有 Owner 提交习惯，不嵌套事务。
2. 原文只能由私有 immutable body Owner 读取；同事务验证 Artifact 的 taskRun/agentRun/attempt 来源与 hash。非成功、缺收据、主体漂移、非 D02 均拒绝。
3. 新建诊断需要当前 Insight 精确版本、合理截止时间、完整 bundle 清册、每条真实 L3 source 授权及正文完整性；原始 requestHash 必须能由实际资料重建。
4. 已提交结果恢复读取 exact 历史诊断，不重新执行过期来源授权；仍校验原文读取权限、actor、InsightRef、ArtifactRef、固定诊断 ID 与内容哈希。这是历史结果读取，不代表后续执行授权。重放 source_requests 不用于重建已提交结果。
5. 明确限制总来源字节数，超限拒绝而非截断。所有读写使用同一个显式连接，不能退回默认数据库。
6. 不新增公开入口、Provider 调用、AgentRun 创建或主库业务数据。受控读取是此时快照；后续生成/审批/执行仍须重新检查当时权限。

## 验证退出条件

针对 actor/tenant/skill/route/input/Artifact/request/hash 漂移和来源不可用验证零发布；验证已提交结果幂等返回、权限仍受控。隔离数据库检查真实 Owner 保存、完整事务回滚和并发单记录。跑关联生成与原 D03 回归，写证据后提交。

下一波：D02 生成执行组合与 TAOR 接续，然后补 D01 正式来源/方法，接通经营计划生成；真实源恢复后执行真实首链，不用合成夹具冒充业务结果。
