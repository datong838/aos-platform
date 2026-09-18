# AM Store 投影证据批量复核方案

## 1. 现场问题与边界

- AM `recoverable_store` attempt `7d6cc3aa-881d-4aff-ac30-58978d06e85d` 持续健康续租，但长时间停留在 Store link 原子提交之前。
- 十二个成员的对象 Receipt 已存在，对象 outbox 为 `objects_written=1558`、`objects_tombstoned=183`、pending=0；本组冻结输入实际为 895 行，derived command 均为 0。
- `EcomConsistencyStore.read_batch_projection_evidence()` 当前先调用 `read_committed_batch_revision()` 完整复核一次，再在第二个事务内重复完整复核；每次 `_reconcile_base_events()` 又按 entity 逐条读取当前记录和 outbox。远程 Store 上形成 O(N) 次网络往返，且同一批次被完整扫描两遍。
- 当前 AM 进程已经加载旧代码。本改动不得中断、重启、重发或改变该 attempt；只服务后续恢复/自然链执行和回归验证。

## 2. 设计不变量

批量化只能减少只读 SQL 往返，必须保留以下 fail-closed 语义：

1. Receipt 必须存在，request hash 与原命令一致；Receipt 的对象/关系计数必须等于原命令。
2. 每个原对象或关系的当前 `payload_hash` 必须与原命令相同；关系端点必须位于同租户、同平台、同店铺，活动关系的端点不得 tombstone。
3. 每个有效原事件必须按 `change_kind + payload_hash` 得到且只得到一条 outbox 证据；event key 不得重复，input revision 必须大于 0。
4. ignored/no-change 批次继续解析到此前的有效事件；无关后续写入不得进入证据集合。
5. derived command 的身份、stream、input revision、Receipt 和有效前序事件校验保持不变。
6. 所有查询继续绑定 `org_id + workspace_id + platform + shop_or_marketplace_id`；不得扩大到跨租户或全库读取。

## 3. 最小实现

### 3.1 `services/aos-api/aos_api/ecom_consistency_store.py`

- `_reconcile_base_events()`：
  - 一次批量读取本命令涉及的当前对象；
  - 一次批量读取本命令涉及的当前关系；
  - 一次批量读取关系端点；
  - 一次批量读取所有候选 outbox 事件并在内存按原 identity 顺序做一对一复核；
  - 保留原 batch event-key 计数门和原错误码。
- `read_batch_projection_evidence()`：不再先调用会完整复核的 `read_committed_batch_revision()`；在同一只读事务取得 Receipt、完成一次 `_reconcile_base_events()` 后计算原批次 revision，再校验 derived input revision。

### 3.2 `services/aos-api/tests/test_ecom_consistency_store.py`

- 先增加多对象批次查询次数上界测试，证明旧实现随对象数线性增长。
- 继续覆盖当前记录漂移、outbox 缺失/歧义、ignored 事件复用、关系端点和 derived 前序事件。
- 加入多对象、多关系的批量等价证据断言，限制 Store 证据读取为常数级查询组。

## 4. 验证与退出条件

1. 新查询次数测试先在旧实现失败，最小实现后转绿。
2. `services/aos-api/tests/test_ecom_consistency_store.py` 全量通过。
3. AM/AL saved snapshot、replacement、successor 相邻回归通过。
4. 对批量过滤条件、事件一对一映射、tombstone 端点规则和 SQLite/PostgreSQL 方言兼容性做代码复审。
5. 当前 AM 仍只读守护；不得用新代码热替换当前进程，也不得把测试转绿当作 AM 终态。

## 5. 风险与回退

- 批量查询可能返回同租户范围内的交叉组合候选；实现必须在内存以完整 identity 精确索引，未命中或多义仍 fail closed。
- `IN` 集合过大可能触及驱动参数限制；本链单批命令受 8 MiB 输入与十二成员边界约束，但测试仍覆盖多项集合。若方言出现限制，改为固定大小分块，不能退回逐实体往返。
- 回退只需还原两个代码/测试文件；Receipt、Store 和运行态均无迁移或数据变更。

## 6. 实施与验证结果

- Red：24 个对象的证据读取在原实现产生 98 条涉及 `ecom_object`/`projection_outbox` 的 SELECT，证明随实体数线性增长且发生两次完整复核。
- Green：对象批次限制为不超过 4 条相关 SELECT；24 个对象加 12 条关系的混合批次限制为不超过 6 条相关 SELECT，证据数量分别与原命令 24/36 个实体严格相等。
- `test_ecom_consistency_store.py` 全量通过；当前记录漂移、关系端点、墓碑、outbox 缺失或歧义、ignored 复用、派生 Receipt 与前序有效事件语义保持 fail closed。
- AM/AL saved snapshot、replacement、successor 及 group relationship/link/retirement/completion 相邻回归通过；环境条件不满足的 PostgreSQL 项按既有标记跳过，没有改写为假通过。
- 当前 runtime host 已加载旧代码，AM 只读守护继续；本改动没有热替换、重启或干预 AM，也没有改变 Receipt、Store、definition、Run 或资源状态。
