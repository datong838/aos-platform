# BG-02 当前签名事件包资格验证

2026-09-14，基线c8d4c174。源包新增导出事件save合同（尚未重新签名发布）。ProductEventQualifiedOwner要求当前Registry资格、唯一增长包、精确导出合同；Registry锁先于安装/来源锁，回调前后重新核验。事件Host服务只接受此qualified Owner，不能用普通SourceOwner构造。PipelineControlServiceFactory复用既有来源依赖构造新增build_event_owner，原build保持。

RED缺新增模块；追加合同布尔负例发现0与false比较问题，1 failed/7 passed后改规范摘要比较。累计78 passed无skip，包括资格桥、服务/当前批准PG、来源Guard、原工厂/发布artifact/注册声明回归。资格桥的来源/安装/签名替身仅证明调用与拒绝顺序，不是真实签名验收。未签名源文档不能授予权限，现有1.7/已签名旧1.8缺本合同继续拒绝事件模式。

AR2扫描1870模块、166分类/93迁出全部错误数组为空；补实际owner/包文档动态路径与关键门禁检查。日志/tmp/product-event-qualified-owner-{red,green,type-red,final,closure}.log。diff通过。主库038、代码041；未部署或注册，无自然Case/Run。

下一波正式HTTP/registry装配：使用require_principal真实subject+scope和当前app control plane的PipelineControlServiceFactory，事件/定时严格分派，资格不成立只拒绝新模式。随后包候选重建、真实角色对应评审、绑定/消费与自然链验收；不使用旧封印替代新schema资格。
