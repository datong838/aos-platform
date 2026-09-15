# SC4-5l6g 主库升级与领域包重装演练方案

日期：2026-09-15
代码基线：`b1ea0e67`
任务权威：`A0V-NATURAL-CHAIN-MAIN-UPGRADE-20260915`，owner=`m1`，有效至 2026-09-17 23:59 +08:00。

## 当前事实

- 重启后独立 `aos-extension` Colima profile 已按无宿主目录挂载规则恢复，环境隔离探针通过；主容器 `aos-a0v-recovery-pg` 已启动，固定数据库为 `aos_meta_head`。
- 只读核验主库当前为 `a0v_038`、532 张 public 表；代码唯一 head 为 `a0v_050`。待部署是连续十二步 `a0v_039..a0v_050`。
- 正租户有九条既有 dispatch，canary 为零；DataRequirement Outbox 当前为空。两个历史安装都 disabled/fenced/unknown，资源 released，受控调度无未停止 Run，因此当前不存在需要迁移器代替业务 Owner 收尾的活动状态。
- `18181/5173/8434` 与 Runtime Host 尚未启动。数据库升级完成前保持关闭，避免旧 schema 与新代码混跑。

## Rules 与停止条件

1. 只对 `colima-aos-extension / aos-a0v-recovery-pg / aos_meta_head` 操作；SQL 再次核 `current_database()`。不切默认 Docker context，不接触普通 Docker 的测试库。
2. 先保存 0600 自定义格式备份，记录字节数和 SHA-256；新建唯一克隆 `aos_natural_chain_upgrade_20260915_test`，从备份恢复并完整升级验收。已有同名克隆、备份、prepare 或 apply intent 时停止检查，绝不覆盖。
3. 迁移执行前要求 m1、当前任务 Lease、source=`a0v_038`、head=`a0v_050`、十二个迁移文件 hash 完全相符。使用数据库 advisory lock、5 秒 lock timeout、每步受限 statement timeout；不 stamp、不跳 revision、不降级。
4. apply 前重新核备份、执行器、克隆、主库版本和业务指纹。先写入 fsync 的 apply intent；提交结果不明只做只读 readback，不重新升级。
5. 既有表内容指纹覆盖安装/运行、九路 dispatch、计划/调度、Case/Run/Task、Requirement/Outbox/Fulfillment、商城 Store 等关键权威。`data_requirement_outbox_delivery` 指纹显式排除本次新增的两个空 completion 列；其他既有列逐行 canonical JSON 哈希。新增历史表必须为空。
6. 克隆和主库都验证 039 的新事件策略约束、040/041/049/050 受控函数、044 完整 event-control dispatch group、042/043/045–048 新表的 RLS/ACL/不可变 trigger、050 双 Receipt 列/约束与 runtime 无直接 UPDATE。canary、dispatch 数、活动安装/未决 Outbox 基线不得漂移。
7. 迁移失败依靠 Alembic 事务回滚并保留备份、克隆和诊断；迁移成功后若服务不兼容，不在原库执行破坏性 downgrade。必要恢复只从已验证备份创建新数据库并显式切换，旧库保留。
8. 230 L0、push、canary 写入、上游商城写入和外部发布均不在本任务范围。

## 实施文件与顺序

### l6g1 主库升级器

- 新增 `scripts/a0v_natural_chain_main_upgrade.py`：`prepare / apply / readback` 三态，复用既有容器连接与受保护写入方式；只处理 038→050。
- 新增 `services/aos-api/tests/test_a0v_natural_chain_main_upgrade.py`：验证精确常量、迁移链/hash、Lease/branch/目标拒绝、结构验收与 retained-proof/replay 边界。
- 状态只写仓外 `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/natural-chain-main-upgrade/`，不提交凭据、备份或主库内容。

顺序：代码测试 → `prepare` 生成备份并在克隆升级 → 独立检查克隆 → `apply` 主库增量升级 → `readback` 二次只读核验 → AR2/Prime/证据提交。

### l6g2 服务与安装控制演练

主库 050 通过后，先用现有私密三平面身份启动受控 API 与唯一 Runtime Host，保持自动模型和无关 Cron 关闭；启动前核新代码 HEAD、签名包根、Host assignment、目录/运行/Web 身份互斥。随后只通过原 Owner 和实际 Receipt执行：当前 fenced 基线读回 → 当前候选安装/配置 → enable → 明确 disable/fence → 重启 Host 后恢复读回 → 卸载并验证资源释放/路由脱离 → 同签名或正式新候选重装、配置、enable。每一步先读当前 etag/generation，未知结果只读回，禁止重发。

卸载重装演练必须保持九条已批准业务 dispatch 的原权威关系，不能用直接 SQL 删除安装、Receipt 或历史；canary 全程零安装、零路由、零交付。若现有候选源码/签名与当前 HEAD 不一致，先构建、签名、资格审查新候选并追加子计划，不能把旧候选冒充当前产品。

### l6g3 真实首链与八工作台

控制演练通过后，恢复栖月汇既有 SSH 严格主机校验的只读隧道和正式 Source Owner。先由经营参谋依据已评审业务材料建立可追溯经营计划，再让真实数据更新自然触发 ProductEvent/Case/Run；后续建议、exact 评审、内容任务、能力调用、产物、人工评审续跑、总控复盘和 Wiki 候选均读实际 Receipt。再按八工作台场景矩阵逐项执行并连续观察。主库升级或安装成功都不能替代此业务验收，也不直接形成发布结论。

## preHash

- `scripts/a0v_configuration_stage_deploy.py`：`819d14a868a3491d03c5710bcd712132adc32f0eb98fe52edc318ba034f48916`
- `scripts/a0v_controlled_source_claim_deploy.py`：`377155566c1a225a9c31fd98d47dae74c23ea70d86a822bd7c6df9ed40ac30c2`
- 十二迁移依次：`2e8d6542...`、`74efd60c...`、`e12996da...`、`4a5d8dbf...`、`4f528757...`、`f8b1870f...`、`38153d82...`、`4999a4a4...`、`cb8a6deb...`、`e74e26f5...`、`fad5b238...`、`9b2d4282...`；执行器和专项测试为 `NEW`。

## 本波退出条件

`prepare/apply/readback` 三态均有不可覆盖的受保护证明；克隆与主库同为 `a0v_050`，迁移前关键业务指纹与迁移后排除新增空列后的指纹一致；新增表为空、ACL/RLS/trigger/function 合同通过；正租户九路 dispatch和当前 fenced 安装基线未被迁移改写，canary 为零；相关测试、AR2 和 Prime 一致。满足后才进入服务重载和领域包控制演练。
