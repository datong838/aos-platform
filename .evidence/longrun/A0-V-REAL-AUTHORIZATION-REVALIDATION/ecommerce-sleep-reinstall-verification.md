# 休眠失效恢复后的新实例验证

基线6fc85ce8。三执行器新增互斥sleep恢复入口，原default/config恢复路径不变；先红5 failed/5 passed，后目标隔离+正式首装回归18 passed。

正式新安装a0fd8e25-cb6f-49e5-aa77-7faddae12099：审批approved@3，apply4a4eea12-214f-4f30-9f18-aaf91e01126d成功applied@4，verify1062a791-316c-4fd2-ac35-1be4abcf80e1成功active@5。generation49427eeb-e9f8-42d5-8588-108e90110beb。

四来源以当前Owner读取为准：responsibility-plan-63c82d2a75614e1b95f1 r2、数据分级r1、budget r1、runtime policy r3。新配置2360b80e-45cb-48fb-83db-c779dea3c63e@1，hash00388910...；configure7069bee9-5479-4589-b244-004e1a161d89成功，enable完成。binding ready/enabled=true/unfenced@4。

05:48:52Z确认跨05:48:31原期限：320.976秒、5次自动续租、3真实容器Running、canaryInstallationCount=0。此前293秒观测尚未跨期限，保留原文件；跨期限确认单独存ecommerce-sleep-cross-deadline-confirmed.json，不以早观测冒充完成。Host v12(pid61252)持续运行。

实际完成休眠失效后的禁入、清理收尾、正式disable、uninstall及新generation安装/配置/enable。此结论只覆盖技术生命周期，不等于真实数据自然触发/经营建议/八工作台经营闭环。没有运行Provider、源端业务动作或发布，不push。

下一波：继续运行观察，同时核对真实数据接入缺口、已安装工作台的产品入口和经营首链前置。已请求原SSH工具/配置位置（不索取密码）；路由登记权限扩展仍待具体答复。不能用旧数据/fixture替代栖月汇实时事实。
