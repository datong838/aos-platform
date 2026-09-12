# 来源选择不可变持久记录与准入接线

2026-09-12，基线40800cb9。承接source-selection-owner-plan.md；当前没有SourceSelectionRevision持久Owner。不能用已验证映射、前端选列或诊断SQL自行授予管道live。

## 合同拆分

services/aos-api/aos_api/pipeline_runtime_control_contracts.py提取PipelineControlContext公共字段与纯校验：scope/pipeline/graph、安装/generation/epoch/configuration、package、SourceConfiguration、Mapping/Schema/Masking、预算和时间窗。现有PipelineRuntimeControlDraft继续持有SourceSelectionRevision引用及原schemaVersion/state/readOnly，保持既有JSON和摘要语义。

新增PipelineSourceSelectionDraft使用同一公共上下文，schemaVersion为aos.pipeline-source-selection-draft/v1，prepared/readOnly=true，不包含自身SourceSelection引用，避免自引用摘要。读取规格由Owner从已安装资产导出，不由请求任意提供。合同本身始终不授权。

## 持久Owner范围（逐步实现，每项通过后接下一项）

1. 新增来源选择不可变记录表，归属双租户、installation/generation、pipeline、稳定selection UUID及递增revision。只追加payload/hash、previousHash、actor、idempotencyKey/requestHash和记录时间；FK绑定安装运行代际及真实source configuration。数据库强制RLS、禁止UPDATE/DELETE/TRUNCATE；不修改任何旧业务行或回退保护。迁移编号在编码前再次检查，计划为当前a0v_021之后的a0v_022。
2. 服务端追加先锁安装，再锁当前binding/configuration/source/graph，调用现有当前配置权限与四源Owner。只有已验证的CurrentFourSourceConfigurationAuthorization可用于生产，不接受HTTP/callback替代权限。运行角色通过原有连接工厂取得，本模块不SET ROLE、不创建角色或复制凭据。
3. 当前安装包锁与选定package严格一致；CurrentRuntimeReleaseArtifacts只读取该published release的digest钉住资产；导出规格与请求Mapping/Schema/Masking exact refs一致。实际SourceConfiguration必须当前、同sourceId及租户。SourceSelection不要求已经有成功同步历史。
4. 同事务计算规范payload/hash、CAS校验previousRef并追加；同幂等键同请求回读原引用，异请求冲突。租户、actor、预算/有效期、source/graph/package/config变化均不允许静默替换。旧修订可审计读取，但当前执行只能使用最新选择与当前状态。
5. 执行接线仍走现有ScheduleRun/Ingress；调用前重新核对安装/权限/预算/时间/SourceSelection/图/源配置，显式列读取，未知结果只恢复原run。该步骤完成前不启用P01，不开放独立任意SQL或live入口。

## 本轮退出与验证

先完成公共合同拆分与来源选择草稿，验证旧合同合法JSON/hash不变、拒绝条件不松动、新草稿无自引用和无批准状态，再进入持久表及Owner。数据库部分需独立PG验证RLS、跨scope FK、不可变、幂等/CAS及重放拒绝；正式部署单独落当前HEAD、schema版本和Owner权限证据。不得以草稿/表存在当成真实同步完成。不push，230 L0挂起。
