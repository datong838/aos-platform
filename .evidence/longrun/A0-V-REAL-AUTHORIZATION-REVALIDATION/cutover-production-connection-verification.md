# 生产切换连接装配验证

基线a9dc8744。新增测试先1 failed/3 skipped（模块缺失）；完成后启用真实PG联合42 passed，覆盖受保护身份、忙事务拒绝、事务结束清理、启动不连接及同一真实registration依赖。git diff --check通过。AR2扫描1825模块，159分类/93迁移，五类错误均空。

主库只读探针详见cutover-production-connection-real-probe.json：维护角色、serializable，org-org/dev-project可见正式组9项，dev-org/dev-project为0。业务写入0，切换阶段执行0。当前API尚未重载，不能把代码装配当线上接口可用。

与方案一致：无DDL、无权限变更、无重试、无业务执行，复用既有Store控制协议。下一波补原键只读Receipt恢复入口及当前权限校验，再接产品阶段接口；现有Store幂等返回不能单独替代当前产品权限。
