# D2d-3c 未知提交只读找回

基线7d07a361，2026-09-14，m1；迁移租约A0V-CONFIGURATION-STAGE-LOOKUP-SCHEMA-20260914。新增038仅一只读函数，原scope+subject+key找到原requestId后复用037权限查询；不调用enqueue、不修改请求或配置。

HTTP GET configuration-requests/lookup使用Idempotency-Key头，静态路由先于UUID路径注册。服务find只查询，未找到404；当前成员/安装标记撤销后不提供旧回执。缺失或未知响应不自动重发POST，不生成新键。

验证：RED确认038未实现；新只读lookup五项真实隔离PG+HTTP十四项+037十五项合计34 passed、7既有warning。已提交后模拟丢响应，按键找回同ID/hash，记录数仍1；未知键不插入，其他subject不可见，撤marking拒绝。真实整体安装路由静态lookup命中find而非get/submit，scope/subject只从Principal，no-store。聚合550条一致，diff检查通过。

未部署主库、未切换Host/API。客户端还没有来源选择/登记操作；下一波次D2d-4实现受限来源目录及产品选择、原键恢复交互。当前总门仍未完成，不能把回执找回当真实经营链路验收。
