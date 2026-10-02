# W5CB4 E17｜签名 BI 模板 approved→active 来源接续方案

## 上位合同与边界

- `231-3` 规定 runtime-apply/verify 把已批准安装推进 active；配置与 enable 均须重新核验当前引用和权限。
- `BG00ds` 明确认证 BI preparation 只创建 Plan draft，不在该入口拼接 Stage、冻结或启用。
- `549` 已用原 Growth 1.13 Registry/签名/安装生产者证明 approved 态的 BI 模板可供草稿准备。此证据不证明 active 后的模板来源。
- 本波只在可销毁隔离 PostgreSQL 和本地 test-only 签名 OCI 链追加跨状态断言。当前真实库只读；不启当前 Host/worker/Provider，不把本地签名升格为正式发行。

## 文件级实施

1. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：在原 approved 安装核 `ActiveBIBusinessResolver` 拒绝；原 runtime-apply/verify 进入 active 后，核同一安装与 exact 模板 ref 可读，并以空 trust、dev-org 做反证。保留原 Growth 1.12 回归。
2. 先跑 Growth 1.13 隔离链。若 active 来源正链失败，仅对证据指向的生产代码写最小修复；不改变 `SignedBIPlanPreparationService` 只产草稿、通用 Plan 冻结或 Host 启动门。若来源本身已通过，记录其与 approved 草稿的安装修订号差异，拒绝把旧 exact ref 冒充当前引用，并将受控 Plan 重绑定留给独立下一波设计与 RED。
3. 跑 1.13、1.12 及相邻模板/BI 测试；复核页面禁入和当前 DB/Host 只读状态；记录 verification 与下一波 Plan Receipt→冻结/配置组装的独立合同检查。

## 完成判据

原安装生产者触发的 approved→active 状态变化使 BI 模板从“仅准备可见”变为“业务可见”，同一安装与模板字节可追溯；安装修订号变化时旧 exact ref 必须失败关闭，不能直接冻结旧草稿；无 trust 和 dev-org 均不可见。结果仅是隔离链代码证据，不代表当前八配置候选、正式身份或自然首链已完成。
