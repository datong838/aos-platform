# AR2-7D Analysis 数据恢复 Run Owner 验证

日期：2026-09-09
基线：`m1@23fc58bf`；方案修订：`docs/m1@72b7795`
结论：`ANALYSIS_RUN_RESUME_OWNER_GREEN`；runtime readiness seal 仍关闭

## Rules 与实现结果

- m1 独占串行、方案先行、最小线性迁移、隔离 PostgreSQL、独立只读复审、证据后提交；未 push，未触碰 230 L0，未访问 Provider/真实数据源/生产数据库。
- 包层 `RESUME_DATA` 不再虚构新 Checkpoint：响应必须原样复用请求的 exact `checkpointRef`，且 `priorCheckpointRef=null`。
- `BusinessInvestigationRunStore.resume_after_data` 只接受当前 `WAITING_DATA/RUNNING`、同一 exact pending `DataRequirementRevision`、无 uncertain command 与正确 expected version；原子生成 `PREPARING/RUNNING` successor 并清空 pending。
- `ar2_011` 接续已有 `ar2_010_source_configuration_revision.py`，维持唯一 Alembic head。SECURITY DEFINER 固定 `pg_catalog,public,pg_temp`，所有新 SQL 对象均显式 `public` 限定。
- 数据库直调对顶层和嵌套 exact ref 做 required-key、JSON 类型、整数词法、NULL-safe 检查，并以 canonical JSON 重算 requestHash 与 state contentHash；Store 在 commit 前完成 raw/DTO canonical 等值和摘要复算。
- Receipt 重放和历史回读不依赖当前 head；同 key 异参、缺 tenant、字符串/浮点 version、缺失/字符串 prior revision、坏 content hash、错误状态、错误 requirement、跨租户均 fail-closed。

## 验证结果

- 包合同与 PostgreSQL Owner 专项：`23 passed`。
- N4/Run/request-data/data-fulfill/analysis-host 邻接：`68 passed`。
- 全 extension runtime：`734 passed, 471 skipped`；skip 为未开启 18432 专用 PostgreSQL 套件的既有基线。
- 独立 PostgreSQL migration：空库 upgrade/downgrade/upgrade、成功、重放、历史 Receipt、RLS canary、Receipt 不可变、非空 downgrade 拒绝均通过：`3 passed`。
- Python compile 与 target diff check：通过；Alembic：`ar2_011 (head)`。
- closure：`1707 scanned / 91 classified / 57 migrated`，`hashErrors`、forward/reverse dependency、bundle cross-layer import、dynamic reference error 均为空。
- memory：`AOS-000571 / GREEN`，Delivery Receipt `865`、Event `2226`、Task Receipt `846`。
- 初次全 extension 误开 `AOS_EXTENSION_PG_TEST=1`，激活依赖未运行 18432 的旧专项套件并出现连接拒绝；按既有基线移除该开关后全量通过。该次失败未写入持久测试库，也不是产品逻辑回归。
- 独立只读复审先后指出 public/search_path、缺字段 NULL、摘要重算、raw/DTO 与数值归一化问题；全部修复并补 runtime-role 直调反例，最终结论为 blocker 清零。

## SHA-256

- `analysis_runtime.py`: `c7f398cd061ff5b4bfb7ab3d02666b17ef86eff61b64f11d0f95f70ebaed4221`
- `ecommerce_business_investigation_run.py`: `f94a0171fd60a39ed21d324f10717717202238449f9355b426f4978361c71278`
- `ar2_011_ecommerce_analysis_resume.py`: `84f55948684fb74fc294687b8ac54240814b2958c659887c1af6972fd227ab95`
- 包测试：`ca14ac78b2f11e9b170e9abcbec13be93512f3e3d8a637a7c0b3969e714730df`
- PostgreSQL 测试：`ff2db212f9ce8dc86e978f3efe3cd9a9d4da67e720594e5aa14cbbb00ad240ac`
- 施工卡：`a19555eee4a6a102adc7e1028f92d85bff1dfed0168fa648668f3bb11f092200`

## 保持关闭的边界与下一项

- 本切片只补底层 Run Owner 与包契约，没有把 Host `RESUME_DATA` execute 接到 `BusinessInvestigationFulfillmentResumeSaga` / `AipTaskStore.resume_run`，不宣称分析恢复纵向链完成。
- 下一切片按 231-6 先写 Host 组合施工卡，再把 Fulfillment/Hydration/Readiness/Mapping/Evidence、Run resume 和 AIP Task/TaskRun resume 放进同一宿主事务；任一步失败整体回滚，重放同时核验两个 Owner Receipt。
