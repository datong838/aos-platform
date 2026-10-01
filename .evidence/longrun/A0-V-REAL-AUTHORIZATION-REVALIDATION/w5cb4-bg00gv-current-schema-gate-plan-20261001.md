# BG00GV 最新代码启动预检的数据库版本门

基线7ae0b0f7/AOS-001062，沿用户每日最新代码重启门、BG00GU真实118→130克隆恢复证据、BG00cg/ch有限API方案。当前库118、代码130。启动器EXPECTED_SCHEMA_HEAD仍硬编码118，导致旧库与最新checkout能被标记预检GREEN；必须在重启前修正，不能只机械更新常量并在下一迁移再次漂移。

## 文件级计划

1. `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py`先RED：旧库版本、空/多行版本、代码空/多head全部拒绝；唯一代码head与库相等通过。保留签名、身份文件权限、external OIDC和worker关闭既有回归。
2. `scripts/a0v_current_preview_http.py`用Alembic ScriptDirectory从API_ROOT/alembic读取唯一head（不连接数据库、不执行migration）；去除手维护EXPECTED_SCHEMA_HEAD。源数据库仍只读，读取alembic_version后立即严格对照，错版返回固定PREVIEW_CODE_SCHEMA_DRIFT；代码迁移目录不可用/空/多head固定禁入。成功report的version来自已核对的实际库，增加codeVersion以便回读。
3. 专项与邻近启动/Registry/Installation测试、compileall、diff check；真实当前signed preflight应从旧GREEN变成明确schema drift（当前118与代码130），不能把拒绝称为已重启。证据先保留BG00GU旧版本预检与新结果。
4. 不启动停机窗口，不更新当前库，不创建角色/OIDC/Secret。只读继续核当前配置入口；未配置合法受限身份时保持现有服务，正式切换另波。

## 约束与风险

本波无数据库/接口变更，浏览器不适用于启动预检代码。现有正在运行的API进程不reload；未来启动因版本差异禁入符合最新代码检查门，恢复入口是已演练的安全迁移及正式身份配置，不能回退硬编码118。旧a0v107首次安装/Registry脚本有意限定首装阶段，不在此波改动。

BG00GU已证明当日真实backup可恢复及全12步克隆迁移，不代替当前零执行窗口、第二份停机备份和正式身份。模型评测用途授权待裁决、watchdog未部署、自然首链未完成。

现场复验发现Alembic延迟导入发生在AOS日志配置之后，会把初始化INFO写入CLI stdout，影响既有整段JSON消费者。将Config/ScriptDirectory导入前置到模块加载时，保留单JSON输出合同，并用真实只读拒绝回包重新核验；不全局禁用日志。
