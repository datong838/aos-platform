# W5CB4 BG00dq｜签名 BI 模板 active 业务读取与产品 code 绑定

## 上位与进入事实

复习 231 主计划、231-3 安装 approved/active 与 binding/enable 分离、231-9 六数字同事职责来源。BG00dp 仅在 BG00dm test-only 克隆证明 approved@3/active NULL 的签名模板配置来源；当前真库仍旧 growth1.11、正式身份/Owner/八候选缺失。旧 `InstalledProductionProfileResolver` 只认 legacy 内容谓词与 `bundle://aos/id@version` URI，growth1.12 runtime manifest/签名源别名均不满足。业务 `AnalysisCompilationRoleReader` 又直接比较 `template.resource_id == domain.responsibility_template_code`（历史静态 ID），使新 exact signed ref 永远不能正向。

## 文件级最小方案

1. 在 `services/aos-api/tests/aip/test_aip_responsibility_template_authority.py`、`services/aos-api/tests/test_ecommerce_analysis_compilation_roles.py` 先写 RED：approved 签名安装只能配置不能业务；仅唯一 active 安装、当前 ReleasePolicy/可信根、精确 lock、签名 alias/artifact/digest/字节/schema 和 `templateId` 与 domain code 一致才允许业务角色读取；错租户、旧版、active 指针漂移、模板 code/签名变化、重复安装、callback 期间变化拒绝。
2. 只在 `aip_responsibility_template_authority.py` 增加 BI 专用 active 读取，复用 BG00dp 签名核验，不放宽通用媒体/旧内容 `_row_matches`，不把 approved 选择结果当 active。`ecommerce_analysis_compilation_roles.py` 把静态 URI 等值检查改为精确 ref 经 active 读取后的签名 payload `templateId` 对齐 domain code，并核对所选安装与当前 draft 安装一致。业务回调前后同样重新读当前权威；不得引入缓存或请求传入的授权布尔值。
3. BG00dm 克隆目前只有 approved 安装，真实正向 active 验收需要另建 test-only 受控状态机演练，先新备份、签名/授权/安装全链校验；本波不会手改 active 指针或当前真库。可先做纯单测与 approved 负向，缺正向完整演练时明确保持任务进行中，不宣称 GREEN。

文件回滚为精确 Git 提交反向修复；不改 schema、不触碰商城源、旧 12 Run、手工 run_definition、230 L0、dev-org 写、Host/worker/Provider 或当前库写。下波需继续正式 signer/checker/三身份/Owner 与自然首链。
