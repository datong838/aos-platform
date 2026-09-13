# BG-02 控制专用签名合同资格

2026-09-14，基线d5a9d02c。新增源包control合同（未签名发布），ProductEventControlQualifiedOwner固定校验control合同，不能继承save合同。原save Owner提取私有合同检查复用既有Registry/release/artifact验证，原行为保持。enable来源snapshot前后资格；disable不读source，读取当前active安装revision/lockHash/overlayRevision及runtime generation/epoch，回调前后资格/etag复核；作用域/当前runtime身份严格检查。

HostTransaction新增精确control Owner无来源桥，来源桥与Guard纳入精确control Owner，PipelineFactory新增build_event_control_owner。没有开放任意回调、raw连接、HTTP或新operation。停用仍需下一层当前管理身份；source失效不等于无需签名安装资格。

RED缺模块；最终42 passed无skip（控制资格7、原资格、Guard、工厂、原保存服务）。具名发布/来源替身只证明资格顺序/拒绝，不是真实签名发布验收。日志/tmp/event-control-qualified-{red,green,final}.log。AR2扫描1876模块、166分类/93迁出各错误数组为空，新增动态必需路径，diff通过。主库038/代码042，未重启/注册/真实启用。

下一波控制Host：连接上述qualified Owner、当前策略/Case/批准、当前停用身份、CAS及控制回执，确认回调失败整事务回滚。后续新operation装配/签名候选/真实独立评审及产品入口，原批次消费/自然Run/首链/八场景/持续观察仍未完成。
