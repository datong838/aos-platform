# UQ6-C API读取身份启动配置

基线4c226874；修改scripts/a0v_product_controlled_api.py、services/aos-api/tests/test_a0v_controlled_api.py，方案先行，11项测试通过，git diff --check通过。实际check返回CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN，专用会话aos_ui_read_transport_20260913、当前角色aos_ui_read_api、数据库aos_meta_head；035缺失请求元数据返回空。

显式资源来源18181及父来源5173；沿用原13版本签名根。productionWebIdentityComplete仍false，不能把专用读取身份检查扩展为全生产身份就绪。Host、迁移、定时写者禁用标志不变。下一步替换现有18181 API进程并验证健康/页面，不重启原Host。

## UQ6-C API配置与实际重启恢复（2026-09-13）

代码b0c0591a，11项测试通过。真实preflight专用UI角色/主库/035查询成功。18181原API40254正常退出，新API61503健康status=ok；原Host6606持续运行未重启。IAB真实重新加载5173/workshop/analyst，页面正常返回“当前工作台入口不可用”，与当前尚未发布安装UI包的状态一致，不声称经营参谋真实页面已验收。

下一波UQ6-D核对原Host启用读取消费者所需前置条件及受控升级方案，保留当前3OCI/原会话和单写者约束；真正更换宿主前须解决原运行会话恢复及UI包真实安装条件。实际业务首链/8工作台/连续观察仍未完成；独立真实审批身份待核验，不造审批人；不push、230 L0挂起。
