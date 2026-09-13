# BG-02 明确启用/停用命令合同

2026-09-14，基线eef0062f。新增ProductEventControlCommand严格只读解析：schema/key/精确policyRef/expectedBindingRevision/enable或disable/approvalRef；scope/运行身份不由命令提供。enable须精确批准引用，disable可无批准引用但不免除后续当前身份/目标权限检查。引用复用PipelineExactRef，拒绝错误用途/替代Receipt、非canonical ID、bool版本、额外权限字段和复制model绕过。

RED缺模块；最终79 passed无skip（命令合同、原pipeline控制合同、请求分派）。日志/tmp/event-control-{red,green,final}.log。AR2扫描1872模块、166分类/93迁出错误数组为空，diff通过。仅合同，没有注册或控制写入；9项旧操作/主库038/代码041/后台服务保持。

下一波实现控制Receipt/CAS存储：沿用automation_schedule_binding为唯一运行状态，原子控制回执不可变，同key恢复、expectedBindingRevision冲突与权限边界；随后真正Owner/当前批准/签名合同/注册/产品意图UI，接原批次消费者与自然Run。业务目标未完成，不以合同测试替代真实启停或经营链。
