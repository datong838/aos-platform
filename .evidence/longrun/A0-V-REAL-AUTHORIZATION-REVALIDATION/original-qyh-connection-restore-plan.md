# 原栖月汇连接恢复核验

2026-09-12，基线ff0e2980。用户本轮再次要求恢复此前已连通底层并继续Loop。找到原项目 `/Users/ddt/work/projects/ai_agent/栖月汇电商多平台/.env` 与 qiyuehui/_ssh_askpass.sh；含明确SSH目标、用户名、端口、数据库字段及SSH_QYH认证配置。原start_tunnel.sh证明历史使用SSH_ASKPASS密码方式，不是最近失败的BatchMode默认私钥方式。

本波不执行原start_tunnel.sh（其StrictHostKeyChecking=no不适合恢复校验），复用原askpass读取器和明确配置目标，严格校验已有known_hosts，单次密码认证、最多一次提示、10秒连接界限、ExitOnForwardFailure、仅127.0.0.1本地转发、无远程命令。目标保持配置内既有身份，不猜密码或更换账号。凭据不进入参数、环境值、日志或证据。新进程成功后只读SELECT 1验证DB连接，并回滚/关闭；不导出商品、不写上游、不发布。

原5173前端已恢复，代理到现18181，8434继续可用。HTTP ontology/health/me与IAB真实页面已通过；此事仅恢复入口，不代表全系统已就绪。5433运行中的aos_meta无meta_source表，不能当作原完整数据库；9月10日事故介质和恢复副本继续保护，不更换当前18435恢复库。

认证或主机校验失败即保留固定错误分类，不循环。成功后下一波通过正式Source Owner恢复连接配置与只读探针，真实数据和经营链仍须后续验证。
