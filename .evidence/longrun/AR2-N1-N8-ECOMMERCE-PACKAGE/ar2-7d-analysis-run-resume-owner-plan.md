# AR2-7D Analysis 数据恢复 Run Owner 施工卡

日期：2026-09-09
基线：`m1@23fc58bf`；方案：`docs/m1@85fddf0`
状态：施工中，不解除 runtime readiness seal

## Rules 与目标

- m1 独占串行；方案先行、最小线性迁移、隔离 PostgreSQL 自测、独立只读复审、证据后提交；不 push，230 L0 挂起。
- 先关闭恢复写入缺失的两个底层合同：包层恢复复用最后 exact checkpoint；领域 Run 新增 `resume_after_data`，只允许当前 WAITING_DATA/RUNNING 且 pending requirement 与请求 exact 相同，生成 PREPARING/RUNNING 新 revision并清空 pending。
- 本切片不接 Host RESUME execute，不恢复 AIP TaskRun，不读 Provider/真实源，也不修改生产 registry seal；完成底层 Owner 后下一切片组合既有 FulfillmentResumeSaga/AipTaskStore。

## 文件与退出条件

- 修改 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analysis_runtime.py` 及包合同测试：RESUME 响应的 checkpointRef 等于请求 checkpointRef，priorCheckpointRef 固定 null；不得声称完成了新 step。
- 修改 `services/aos-api/aos_api/ecommerce_business_investigation_run.py`，新增严格 `resume_after_data` 与历史 Receipt 回读。
- 新增线性迁移 `services/aos-api/alembic/versions/ar2_011_ecommerce_analysis_resume.py`（接续既有 `ar2_010_source_configuration_revision.py`），扩展 operation CHECK 和受限状态函数；固定 WAITING_DATA/RUNNING → PREPARING/RUNNING、相同 pending requirement、无 uncertain command、revision+1、租户/RLS/不可变 Receipt。
- 修改领域 Run 单测与 PostgreSQL 状态机测试，覆盖成功、重放、异参、旧 version、错误 requirement、非 WAITING_DATA、跨租户、回滚和非空降级拒绝。
- 数据库入口必须以 `pg_catalog,public,pg_temp` 固定解析顺序并显式限定 `public` 对象；SQL 直调必须用 required-key/type 与 NULL-safe 比较拒绝缺字段 payload，不能依赖 Python 模型校验。
- 数据库必须以 canonical JSON 重算 requestHash 与去除 `contentHash` 后的状态摘要；Store 在 commit 前以 canonical hash 完成 raw JSON/DTO 等值与摘要复算，数据库整数词法校验拒绝字符串、浮点数字等模型归一化漂移。
- 运行包/Run专项、migration single head、N4/DataFulfill/Analysis Host 邻接、compile/diff、closure、memory validate；任何 Owner 不完整则保持 fail-closed。
