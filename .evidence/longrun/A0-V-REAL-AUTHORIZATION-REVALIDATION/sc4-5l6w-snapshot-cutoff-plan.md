# SC4-5L6W 自然首链的快照时间与组入口补强

2026-09-16，基线 m1 6c3d95b4，AOS-000573。Rules：方案先行、原Owner、双租户、Receipt-first、单写m1、不push、230 L0挂起。承接 snapshot-resume-design.md 的 l6g 真实首链，不能代替全业务验收。

## 真实问题与保留事实

J 已自然生成 Run analysis-e5b19a5fe290ce1bf60d5038cb1d6cf6；08:25读库仍为1 accepted、12 needs_attention、52 pending，事件Policy7 disabled。原源run scr-bddff0a74c2a4365的快照组成员计数0。现有单路P02调度没有生成完整十二源组。初始化使用事件created_at截秒作为cutoff，而数据路由要求原组read_completed_at精确相等。旧组合夹具主动对齐两时钟，因此不能证明自然时间接续。

现有Run、Task、失败Outbox、Occurrence与Receipt全部保留。禁止回写旧cutoff、补造历史组、重放失败Outbox、以新Run冒充原Run恢复。历史十二源同事务快照不可事后重建；原任务后续必须走正式需求修订/取消与后继任务语义，尚未实现或验收前保持暂停，不宣称已恢复。

## 连续实施清单

1. W：给原 PipelineSnapshotGroupLocator 增加 discover 只读入口，从原source run查唯一不可变快照组并返回原read_completed_at。与现有read共用全部租户、角色、manifest、成员、时间验证；read继续强制expected_cutoff精确一致。新增入口不提供current权限，不写表、不消费源、不放宽旧read。隔离PG用真实十二源Owner提交验证，不使用事件时间对齐。
2. X：分析初始化在原source current守卫内选择原组时间，并将组身份/manifest纳入准备前后fingerprint。先补完整产品契约：无组事件不得进入无法交付的Task；处理已有历史Receipt时按原冻结合同恢复而非重新计算。补独立时间测试和原启动回归后才接入。
3. Y：完整十二源调度产品接线，复用ControlledSnapshotGroupIngress与原GroupCompletion，注册/配置/调度恢复均由原控制Owner；正常产品调度无需开发者创建run或拼group。新增具体文件与权限审查后编码。
4. Z：同Case已有活动Run时的事件等待/归并，保留单活动Run约束和每次来源，不再用unknown表示可预期业务竞争。原失败任务的正式需求修订/取消合同及原状态Owner检查另登记；禁止直接改业务表。
5. 接续：新鲜真实全组更新→经营建议→exact评审→内容任务→能力调用→可读产物→评审续跑→复盘Wiki，再八工作台与连续观察。

## W 文件和验收

修改 services/aos-api/aos_api/pipeline_snapshot_group_locator.py；新增 services/aos-api/tests/extension_runtime/test_pipeline_snapshot_group_locator_pg.py；更新本方案、snapshot-resume-design.md和docs两份接续清单。无迁移、无全局配置变更。

Red：旧类不存在discover，测试失败。Green：十二源真实Owner组输入可定位，保存的微秒精确保留，旧read匹配通过/差1微秒拒绝；单源无组返回None；canary无泄漏；角色或scope拒绝；第二次读取不再读源、不增加记录。外部商城数据和安装资产仍named fixture，不能当现场链完成。

风险：discover本身不能证明组当前可执行，调用者仍必须走原Owner；不会将此辅助接口直接接到现有失败任务。回滚只撤回新增入口，旧read签名/行为保持。

## 08:29 现场配置核查

主库meta_schedule仅存在P01-shop-qyh和P02-product-qyh两条受控调度，均disabled。302表可浏览不是十二源组调度完成证明。后续Y需要正式补齐源选择/配置/审批/组调度，不能只改截止时间或把现有两路算完整。

## W 验收结果

Red：1 failed，旧类没有discover（/tmp/aos-snapshot-locator-red.log）。Green：新增定位专项与既有DataRequirement路由共4 passed / 244.38秒（/tmp/aos-snapshot-locator-green.log）；完整迁移的隔离PG，原组Owner生成十二源输入，源/资产仍named。验证微秒精确匹配、错误cutoff拒绝、无组、角色、双租户隔离及零重读；原exact数据路由/unknown回读及漂移拒绝回归通过。git diff --check通过。主库业务记录无修改，J未恢复消费。

下一波X已形成sc4-5l6x-analysis-source-clock-plan.md，接入原组时钟并去掉组合夹具的时间对齐，然后继续Y/Z及真实业务闭环。
