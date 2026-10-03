# W5CB4 E17-s3o-r｜ToolBinding 原发行 Receipt 缺口 RED

日期 2026-10-03。按同名文件级计划复习 231/231-9/128 与原 Store/路由/迁移后，只在自动销毁 PG135 执行。

原 `AipAssigneeResolutionStore.upsert_tool_binding` 写入 test-only `ToolBinding` version1 后，读回绑定确实存在，但同 tenant/binding 的 `aip_agent_registry_receipt.operation='tool_binding.upsert'` 数为0；预期1，首次 `pytest` exit1，`assert 0 == 1`。原 Resolve 另有 AssigneeResolutionReceipt，但它属于解析，不是此写入的发行回执。将 RED 保留为 `strict xfail` 后，与 s3o-q/W-L20/W6 相邻跑 exit0，12 passed/1 xfailed/7既有 warnings。没有为刷 GREEN 直接 INSERT 伪回执，也没有在当前真库写入 ToolBinding。

复审：原 upsert 缺 sourceRef/批准/installation/actor/idempotency 及同事务发行回执；HTTP role 和 s3o-q 版本 CAS 不能替代这些权威。现行普通 runtime 在当前库仍有 ToolBinding 宽写 ACL。给原路径一个独立数据库账号只解决连接身份，无法证明来源。下一步须在文件级方案里冻结 RegistryReceipt 是否复用、exact requestHash/回放、发行者、原 Agent/Capability/Tool 正式来源与消费时当前性、独立窄 ACL，再做隔离正反链；当前库迁移仍先新全备/克隆/零执行窗口。此 RED 与 test-only 绑定不构成正式六 Binding、八配置、Host 或自然首链验收。Goal active，不 push。
