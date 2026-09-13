# 专用读取身份实际部署验证

## UQ6-B 实际专用读取身份完成（2026-09-13）

执行器43e72f62；19项检查通过。恢复副本aos_ui_read_20260913_test和主库aos_meta_head均实际返回UI_READ_TRANSPORT_IDENTITY_VERIFIED；仅可切换aos_ui_read_api，正租户原主体核验成功，缺失请求返回空。subject-mismatch、negative-tenant、direct-table、host-function均实际权限拒绝。19关键业务表指纹一致，队列0、业务写入0。私有身份保存在仓外0600文件；共享证明只含摘要。

这是技术读取身份，不是业务成员或独立审批人；未发布安装growth1.8，未重启Host，未完成真实业务读取或八工作台闭环。下一波UQ6-C把专用身份摘要及两端资源来源纳入受控API启动检查，再做服务恢复验证。m1串行、不push、230 L0挂起，总门仍AOS-000573。
