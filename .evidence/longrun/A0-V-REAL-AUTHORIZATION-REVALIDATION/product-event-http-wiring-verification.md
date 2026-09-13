# BG-02 已认证请求的事件保存装配

2026-09-14，基线 f98a1551。新增请求级 EventAwareSchedulePutHostService，Principal subject/scope 固定，精确 PipelineControlServiceFactory 延迟构造 qualified Owner；仅 event schema 分派事件服务，未知 schema 拒绝，旧定时服务和其他八操作不变。正常 HTTP dependency 使用现有 app control plane，不接收调用者提供的来源回调。每个回调检查 scope；服务缓存不缓存当前权限结论。

RED：新增模块缺失。GREEN：72 passed（新分派/HTTP/原 runtime registry/adapters/Host ports），无 skip；测试替身只证明请求接线，不代表真实发布包/业务链验证。日志 /tmp/event-http-red.log、/tmp/event-http-regression.log。AR2 扫描1871模块、166分类/93迁出，各错误数组为空；git diff --check通过。

主库038、代码041，未迁移、未重启API/Host、未注册新候选；旧已签名1.8仍不能覆盖新增合同。整体未完成。下一波核对事件保存的正常产品命令构建与原幂等键恢复，先补产品入口方案，再接事件绑定/消费；随后真实首链、八工作台与连续观察。
