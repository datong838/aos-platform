# 栖月汇恢复包受控目录接线

依据当前栖月汇全系统恢复方案及已登记恢复兼容清单。Task qyh-restored-bundle-alias-20261011，唯一施工 thread 01a107a2-e9e4-7670-bc44-1144fa9b27e2，m1。租户 org-org/dev-project；电商域模板与栖月汇实例配置仍分层。

事实：新 core1.4.3/Growth1.13.0 经现有 Registry 创建和验证，不可变 sourceRef 使用 a0v-qyh-current；production control_wiring._allowlist_roots 目前缺少该别名，恢复 API 无法通过相同来源加载这些包。

最小修改 services/aos-api/aos_api/asset_registry/control_wiring.py：仅在 AOS_BUNDLE_ROOT 已配置时，把该固定别名映射到同一 server_root。保持已有三个 server aliases、catalog 与 trust-root/signature/current-release 校验不变；不自动扫描路径、不从请求提供任意根、不增加默认配置。

测试 services/aos-api/tests/asset_registry/test_control_wiring.py：现有 builder 契约增加精确别名，先 RED；未配置时保持仅 catalog。专项和相邻 loader/signature/release-policy 回归，并使用两个新包实际签名树，通过 production alias 配置原 ManifestLoader 与 ReleasePolicy 只读验证。

证据目录 .evidence/qyh-restored-bundle-alias-20261011。只读核对已加载647表库：新两版本仍 validated、同身份 publish 无事件，数据变动仅登记 Registry 表。发布身份待用户提供，不伪造其他 actor；该接线不授安装、配置、Host、worker、Provider 权限。

本波不改变数据库、当前API/Web进程、运行门或已有正常包。回滚仅撤回新增映射及相应测试期待，不触及不可变 Registry 或任何卷。交付条件是代码/方案一致、实际签名只读加载、专项相邻通过、m1精确提交与Delivery及上下文同步；全系统恢复/八页面仍由原 ACTIVE Task 验收。
