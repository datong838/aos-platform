# ADR-AIP5-001：运行记忆与知识权威边界

状态：Accepted（AIP-5 E0）
日期：2026-08-12

## 决策

1. 运行记忆只有 Working、Episodic、Semantic 三层。
2. Working 的真源是 Task/Checkpoint；Episodic 的真源是 Run/EffectReview/Evidence；Semantic 的真源是经治理的 O1 Wiki/KnowledgeSubject revision。
3. Procedural 是版本化 Skill/Logic/Policy/Playbook 资产，不建运行时 Memory 表；Shared 是经过授权、脱敏和适用范围治理的投影，不建第四套存储。
4. `aip_long_memory.py` 和 `ontology_wiki_engine.py` 的 singleton 仅为历史兼容/测试适配层，不能作为 AIP-5 完成证据、跨进程真源或跨租户共享路径。
5. 外部研究、人工经验、客户聚合与运营结果只能先形成 Artifact/MemoryCandidate；正式 Semantic 写入必须精确绑定 Eval report revision/hash、Draft 与 ApprovalEvent。
6. scope 只来自认证上下文；请求 DTO 不接受 org/project。PostgreSQL authority 在 E1 建立并强制 RLS/FORCE RLS。
7. 全文/向量索引仅保存可重建 scoped refs；撤回、过期、冲突和无权限由 authority 查询层失败关闭。

## 当前代码真值

- `aip_long_memory.py`：可写内存 singleton，进程重启丢失且无 TenantScope；只保留兼容，E1 后不得被新生产路径调用。
- `ontology_wiki_engine.py`：无 TenantScope 的内存 Wiki/Version singleton；AIP-5 只通过 O1 公共 authority/写契约适配，不直接晋升到该 singleton。
- `aip_taor_loop.py`：Working 仅组装当前上下文，Semantic/Episodic 仍为空占位；E3 才接 KnowledgeQuery，E0 不伪称已检索。

## 后果

- E0 只冻结严格公共契约和机器测试，不注册 API、不创建 Store、不做 migration。
- E1A 只有在本 ADR 与契约测试 GREEN 后才能建立 Candidate authority。
- 旧 API 若继续暴露 singleton 数据，必须明确标注兼容/非权威，且不得被 AIP-5 页面当作正式知识展示。
