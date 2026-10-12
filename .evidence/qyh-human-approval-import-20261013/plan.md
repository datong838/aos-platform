# 对话人工审批导入当前栖月汇恢复安装

用户当前明确：唯一真人由其授权审批，开发代理记录状态即可；建立本机登录入口，但不需再审批一次，并要求立即继续。该最新指令覆盖此前必须等待另一登录主体的执行判断。记录审批者为human:conversation-owner:01a107a2-e9e4-7670-bc44-1144fa9b27e2，明确它是本对话实际真人审批来源标识，不是新建认证账号、OIDC身份或借用既有管理员。执行代理是原dev申请/开发者；原maker-checker仍区分开发申请人与实际真人决定。

仅ab2fd72f-d81c-400d-bbbc-e1589a159d6b submitted revision2/精确四包/四变更hash。通过原InstallationService.approve与RuntimeReleaseRevalidator、原Store事务/CAS/幂等，角色asset-install-approver表示用户明确授予本次人工维护审批权限，不能声称来自JWT或会员表。不直接UPDATE state、不造登录凭据、不放开API。由原父Task活跃维护租约覆盖当前库操作，子Task仅本目录证据。审批权限不扩为Host/worker/Provider/商城/旧Run/预算执行或八配置通过。

执行前只读核当前请求、前驱5、161/650、全禁入与实际Docker卷身份；完整一致备份+第二份SHA校验、原650表前后指纹对比。每次只有一个排他intent，不重发未知结果。批准后只读独立连接核approved revision3与原决议4hash/current主体来源，容许变化仅安装head/revision/event/decision/command表，其余645表不变。用户登录入口继续已授权建设，不以该导入伪称登录已可用。正式运行准备/apply/verify/配置仍独立待验收。
