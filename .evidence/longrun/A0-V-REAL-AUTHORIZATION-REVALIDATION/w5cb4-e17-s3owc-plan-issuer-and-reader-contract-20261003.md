# W5CB4 E17-s3o-w-c｜职责 Plan/Receipt 独立发行与只读消费合同

日期：2026-10-03。上位复习：231-3/4/5/9、栖月汇经营分析执行方案，s3o-v/w-a/w-b 的 ACL/原行锁/隔离锁探针。当前真库 `a0v_135` 只读；不得在本波给代码新增 migration 头后逼迫真实库迁移。

## 文件级步骤与判据

1. 只读盘点 `aip_production_contract_store.py` 的 `create_responsibility_plan[_in_transaction]`、`revise_*`、`freeze_*`、`_head`、`_advance_head`、`_receipt`，以及全部调用它们的产品/BI 路径；`w2_001_brief_evidence.py`、`w2_002_eval_responsibility.py` 的 ACL/RLS/trigger。列出每条路径的连接角色、前置依赖读取、写表、Receipt、幂等和锁序。确认是否有原 Store 外的合法 head 写者。
2. 在独立 PG 临时 schema 的 `services/aos-api/tests/extension_runtime/` 中复用真实原 Store/读者与真实角色，不借 `aos_app` 超级用户或 `lambda True` 模板 resolver 申报正式完成。先 RED：只读 runtime 对原 `FOR SHARE` 正向失败；原宽权 runtime 能直写同租户 Plan/Receipt；不改幂等键、不造业务成功。
3. 设计独立不可登录 issuer 角色和独立登录映射的最窄权限。只允许合法受限命令访问原 Store 的 Plan/Receipt 原子操作；runtime 只有 SELECT，不能直写 head/revision/Receipt。数据库触发器覆盖 head 的 INSERT/UPDATE/DELETE，锁键包含租户与 planId；只读消费在相同短事务内先锁再查当前 revision/hash，所有多 Plan 按稳定顺序。提交结果需同键重放/CAS、跨租户、失败回滚、并发发布、Receipt 防伪造反证。
4. 正式 migration 与当前实例切换是独立安全波：新一致全备及独立恢复校验、ACL-faithful 克隆全链、零执行窗口、正式 OIDC/独立凭据/签名来源、安装/Host Owner 对账；未齐备不得给当前库写入或开启 Host。原 API/Web 当前可用不代表首链。

本波先完成步骤1并定义原 Store 隔离 RED 的精确夹具；若任何原依赖本身需要高权限或 mock，先留可复核失败，不改产品/公共协议求绿。浏览器仅在适用的配置入口/UI 波进行，底层 issuer 本波以数据库与 API 合同证据为准。

## 只读盘点的新增事实

- 原 Plan 写者除 `AipProductionContractStore` 的 create/revise/freeze 和 BI 包裹路径外，还有 `aip_responsibility_assignment_store.py` 的 successor 创建：直接 INSERT Plan head/revision，随后写自己的 successor 权威，并非通过原 ProductionContractStore 的 Plan Receipt。触发器必须覆盖这条路径，或对正式 Config 源排除未带独立发行证明的 successor；不能只修改原 Store。
- `aip_production_contract_receipt` 是共享表，`aip_content_draft_store.py` 也直接 INSERT。简单给独立 Plan issuer 独占整张表 INSERT 会破坏现有内容产物路径；简单保留 runtime INSERT 又允许伪造 Plan 操作的 Receipt。需按 operation/签发来源在数据库边界区分，原共享表不能仅靠 `operation` 文本和相同租户来做验真。
- BI 路径 `ecommerce_business_investigation_aip_authority.py` 包裹原 Plan Store 的三种 in-transaction 调用；HTTP `routers/aip_production_contracts.py` 还有原 generic create/revise/freeze。两路都需要同一正式 issuer/权限与锁序，并继续保留原 Receipt/幂等。
- 这些新增写者让本波的下一 RED 夹具必须分别覆盖：generic/BI/successor 三条 Plan head 写路，以及共享 Receipt 中其它合法生产者。未证明兼容前，不提交正式 migration，不切当前 ACL。
