# W5CB4 BG-00bn｜系统策略 ActionType 元数据与数据库写门施工方案

## 上位方案与当前事实

AGENTS.md、aos-engineering-delivery、231/231-5/231-9、BG-00bh～bm。当前权威 PG `a0v_114`，全局 `meta_object_type/meta_action_type` 两表均0行；`aos_runtime` 有 INSERT/UPDATE/DELETE。通用 API/插件对五 ID 已保留，但不足以阻止 DB 直写。当前库只读；本波只在隔离 DB 演练，代码迁移头高于当前库期间不重启当前 API/伪称最新。

## 精确文件与合同

1. 新增 `services/aos-api/alembic/versions/a0v_115_policy_system_action_metadata.py`，`down_revision=a0v_114`。本波只建立五固定 ActionType ID 的数据库保留写门，**不插入** `NetworkPolicyRevision` ObjectType 或正式 ActionType 行。当前没有正式 Producer/产品预览，先插行会把不可用动作暴露为可选择目录项；元数据生产必须与正式来源同波。迁移不得改普通行或当前 Action/Approval 数据。
2. 迁移新增 `meta_action_type` 的 BEFORE INSERT/UPDATE/DELETE DB trigger：对五固定 ID，`current_user=aos_runtime` 以及其他非表 Owner 均拒绝；对普通 ID 不改。Owner 仅在未来正式受控迁移中可插入系统行；生产代码仍由 BG-00bl API/插件门拒绝。当前 DB 登录 Owner 凭证可绕过该触发器，后续需独立数据库角色硬化，不能把本门视为绝对隔离。
3. 修改 `services/aos-api/aos_api/aip_action_service.py`：通用 create_proposal/create_draft/revise_draft 对五固定 ID 失败封闭，避免元数据出现后被通用 Proposal 产品入口伪造正式策略批准。专用未来 Producer 必须重算 BG-00bj exact target，并使用独立 API/权限/预览，不通过通用入口。
4. 新增 PG 集成测试：在 disposable/test-only `a0v_114` 克隆应用迁移；核五固定行仍为0、DB runtime role 的 INSERT/UPDATE/DELETE 拒绝和普通 ID 不受影响；通用 Proposal 路径在接触 DB 前拒绝；现有通用 Action 回归。重复迁移/漂移必须失败，不静默覆盖。
5. 用当前 a0v114 的独立一致 dump + SHA/TOC 恢复一个新 test-only clone，完整 Alembic 升到 a0v115，回读元数据/迁移/原始表计数与关键安装不变；源库始终只读。保留备份与克隆证据。当前库升级放在独立 BG-00bo，需再次一致备份、全链演练及零执行窗口。

## RED/回滚与边界

先测试失败再实现。迁移 downgrade 抛错，保留不可静默回滚的系统元数据；恢复靠事前独立 dump。测试执行不调用商城源、旧 12 Run、Host、worker、Provider；五类 Store active 禁入不变。完成代码与隔离验证、专项/累计回归、方案复审、verification、精确 m1 提交与上下文更新。
