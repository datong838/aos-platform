# BG-02 当前来源事务桥验证

2026-09-14，基线f4452f00。HostTransaction新增专用原连接来源Owner桥，不暴露connection/cursor/commit；ProductEventPolicyDraft.validate_policy关联包策略摘要与来源上下文；ProductEventPolicyGuard在当前Owner回调内核对实际compiled mapping、选源版本、scope及dispatch安装/代次/epoch，在同步业务回调前后用数据库时钟检验事件有效窗。无新运行注册或审批权威。

新增模块缺失RED后37项通过；加入原Host端口、来源Owner及PG回归，累计109 passed，无skip。桥测试使用具名fake Owner，证明同一连接传入与拒绝/过期/延迟回调边界，不能据此声称真实权限已通过。原Host PG与来源存储专项继续通过。AR2扫描1866模块，164分类/93迁出，全部错误数组为空；diff与memory-validate GREEN。

日志/tmp/product-event-source-guard-{red,green,final,closure}.log。主库038，Host/API未重启，未产生实际event策略或自然Case/Run；当前真实首链、八场景、连续观察仍未完成。

下一波在这个来源事务桥内加入当前Case/Profile和原ActionApprovalEvent精确校验，再同事务调用事件Store；不能用固定假actor或包命令自报actor作为身份。新操作未完成前不改现有注册封印；产品入口/真实发布及运行接管之后再执行自然链验收。
