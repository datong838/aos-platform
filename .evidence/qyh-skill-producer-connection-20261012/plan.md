# 私密producer连接入口

Rules：AGENTS.md、231、已批准完整Skill合同与D-wave。上一wave85native通过的是内部完整终结，不是正式准入。候选一原卷维护另门；候选二此连接与部署条件，选择二。

新aip_skill_eval_producer_connection.py使用AOS_AIP_SKILL_PRODUCER_CREDENTIAL_FILE，受控0600本人文件，schema aos.aip.skill-producer-identity/v1、role aos_skill_eval_finisher。配置缺失None/不回落runtime；无secret参数/环境/日志输出。原aip_eval_writer_connection.py只提取保护文件解析器供复用，旧wrapper/错误消息/one-role验证全部保留；不复制第二套校验。新connector原生核独立两角色LOGIN/数据库，检查事务回IDLE后yield，caller显式commit；finally仅close，不隐式commit或重放未知操作。

新增test_skill_eval_producer_connection_pg.py：未配/错schema/权限/重复/符号链接先拒绝，不连接；实际新LOGIN、两角色/错库/管理员拒绝；返回IDLE并测试明确commit、未提交退出rollback。标准隔离UUID全库和临时角色/测试私密文件，不生成真实账号/密码/角色，不改全局配置。此组件不授Owner/审批/预算/签名/finisher权限或外部执行，正式来源仍需既有受支持配置。红绿、旧loader及上一wave原生累计，精确交付。
