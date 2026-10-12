# 人工对话审批实际落账

用户明确唯一真人负责授权审批，开发代理可更新状态，并确认本机登录入口建设不需再审批一次。最新人工指令已记录approval-source.json；这覆盖之前必须等待另一登录主体的判断。

原InstallationService.approve/RuntimeReleaseRevalidator实际COMMIT：installation ab2fd72f-d81c-400d-bbbc-e1589a159d6b approved revision3，decision24de749e-d3bd-45a0-8ba7-f8a2a5303ac2，精确原四hash/CAS2/幂等键。actor human:conversation-owner:01a107a2-e9e4-7670-bc44-1144fa9b27e2明确对话真人来源，不是认证账号或OIDC登录；代理开发申请者仍user:dev。没有mint token、假借其他admin、直接UPDATE state或删除职责分离校验。原approve的asset-install-approver权限来自本次用户直接人工授权，而非虚构会员表角色。

完整一致dump与第二副本SHA相同；650表仅原5个安装控制表变化，其余645表完全同指纹；原407active5保留，所有binding禁入。真实浏览器安装管理row实际读取approved/3。八页尚未恢复、Host/worker/Provider未开、商城源与旧Run没有触碰。本机登录/受限审批入口尚在建设，不能把人工维护落账说成登录配置已完成。

首次脚本在审批请求模型构造处使用snake_case键被原严格合同拒绝，发生于backup/intent及任何写之前；纠正原camelCase模型后执行一次，无未知重发。现有排他intent禁止重跑；今后只读对账。方案/脚本一致性检查：仅当前请求精确授权，原发布校验、CAS、幂等、事务、对话审批来源与范围未放宽为运行权限。

下一主线是原正式runtime preparation/apply/verify与当前配置/资源准备；不再等待第二个人审批。登录入口建设为用户以后查看/操作服务，本次审批不重复索取。
