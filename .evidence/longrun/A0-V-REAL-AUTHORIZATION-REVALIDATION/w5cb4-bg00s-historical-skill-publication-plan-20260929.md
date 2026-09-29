# W5CB4 BG-00s｜历史 Skill 发布记录的新修订消费禁入方案

## 依据与只读定位

231 首链和 AIP-4 E2 要求同租户、exact Eval 与签发来源可复核。BG-00q/r 已封正式 Contract Runner 与 E2 的新 Gate/Event，但旧 PASSED Gate 和旧 published PublicationEvent 若已存在，`AipSkillPublicationService.publish_evaluated_revision` 仍可只凭状态、目标引用和 route/logic 检查写出新的 published Skill revision 与 RegistryReceipt；`AipSkillBindingReadinessService` 后续只读 published 修订、Gate 与 Event 的浅层状态，安装目录则汇总 published/active。当前权威库 `org-org/dev-project` 的 Gate/Event/published Skill 均 0，未发生该效果；代码仍存在历史记录再发行路径。

## 本波文件级最小改动

1. `services/aos-api/tests/aip/test_aip_skill_publication_service.py` 在隔离 PostgreSQL 用测试字节生成既有 Skill Report，精确种下同租户、同 target 的历史 PASSED Gate 与 published Event，再调用 `publish_evaluated_revision`；RED 要证明当前会新建 Skill revision/Receipt，而预期应在写前拒绝。测试还要断言源 evaluated 修订保留、无新的 published 修订/Receipt，跨租户或撤销行为不借机放松。
2. `services/aos-api/aos_api/aip_skill_publication_service.py` 在同一 scoped transaction 已核 Gate/Event exact 且任何新修订插入前，复用 E2 的 Gate/Report 复验函数；当前该函数会因缺独立 Judge/Target signer、撤销和执行 Receipt 权威而拒绝 Skill。读取完整 Gate 行以供复验，将 E2 拒绝映射为现有 Skill 转换阻塞。现存幂等 Receipt 的同 key 只读回放维持；不得删除旧 Gate/Event/Skill 或伪造新身份。只改该消费入口，避免另建权威系统或影响 LogicGraph 发布。
3. `AipSkillBindingReadinessService` 和安装目录本波只读审计并登记风险。当前没有历史 published Skill，且本波关闭新修订入口；若隔离试验证明预存 published 修订可经 Binding 激活，下一波在 Binding/安装边界做独立 RED 与最小修复。不能把当前库零行当作未来的永久保护。

## 验证和退出

先 RED，再最小实现，跑 Skill/E2/Runner/Binding/安装相邻测试、编译及差异检查；当前库只 `BEGIN READ ONLY`。API 用最新 m1、现有正式签名 Receipt 重载核健康，不重启 PG/迁移/Web。G2 正式 Eval 内容、Judge/Target 签发 Owner、执行 Receipt 和隔离 MinIO 真实读回仍是正向主线缺口。D01、Host/worker/Provider 与首链继续禁入，不读商城源、不重放旧 12 Run、不动 230 L0、不 push。
