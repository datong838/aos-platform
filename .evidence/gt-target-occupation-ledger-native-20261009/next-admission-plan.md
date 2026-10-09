# 下一步候选与实际准入前置

候选一：为已登记 actual occupation ledger 验证未来状态事件的可信准入边界。依赖当前可信 Target call 与根/首事件；先调查原物理账户及 bucket 锁顺序、实际计数来源，形成文件级设计和 RED。只允许独立全量原生库；当前工件不会计入实际 inflight，也不会获准 COMMIT。

候选二：已登记 Judge typed proof 与 parent budget 细化。依赖原 Source/newJudge 正式批准及已完成计划四腿，不通过空价格补零或客户端费用扩大权限。现有 null 价格须保留；实际费用分配与 Usage 的可信输入尚须专项验证。

选择候选一的安全调查：核对物理账户 guard 与双 purpose bucket fences 的既定顺序，并检查实际 inflight 是否已有可信持久来源。原 prepare 流程会先取得 Source 与 physical guard，再取得 bucket fences；新账本首事件不能直接替代实际 admission。未来 actual_admitted/unknown/释放事件必须有独立 server-derived 证据和全局等待后 current recheck，禁止客户端状态或依靠 TTL 释放 unknown。本记录只提出调查范围，不宣称完整锁图或 lifecycle 已实现。
