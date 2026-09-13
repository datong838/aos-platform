# UQ6-B 专用读取身份执行器检查

基线90e89719，m1单写；19项专用身份部署及真实连接器权限/回滚检查通过，7项既有依赖警告。git diff --check通过。

本提交包含scripts/a0v_ui_read_identity.py及services/aos-api/tests/extension_runtime/test_ui_read_identity_deploy.py。实现与先行方案一致：先恢复副本再主库；凭据私有持久化；仅授专用读取角色；禁止覆盖不一致身份；异常安全输出。验证回执包含身份文件摘要供后续启动核对，绝不包含凭据。

尚未执行实际角色置备，不代表真实安装、业务首链或浏览器验收完成。下一步执行clone，成功后main，并落实际数据库拒绝证据。
