# 原入口与栖月汇连接恢复

2026-09-12，基线ff0e2980。用户指出以前底层已通，要求主动找回并持续开发。本次找到原栖月汇电商多平台/.env与SSH_ASKPASS脚本。历史采用密码认证；9月11日失败的是默认私钥/BatchMode，两者不能混为同一连接路径。

06:34:07Z按既有原配置、同目标/身份恢复，StrictHostKeyChecking=yes、一次密码提示、10秒连接界限、只绑定127.0.0.1:13306，无远程命令。SSH退出0、本地监听true，MySQL START TRANSACTION READ ONLY + SELECT 1成功，已回滚/关闭DB会话，总耗时1.188秒。密码由原askpass读取器输出给ssh，未进入参数、环境值、日志、文档或Git。未运行原脚本的宽松主机校验，未导出数据、修改源库或发送/发布。证据original-qyh-connection-probe.json。

5173原端口此前无监听；现用同仓Vite启动并代理18181。/ontology HTTP200、/api/v1/health ok、/api/v1/me确认org-org/dev-project，IAB tab9本体页面可打开。8434原恢复入口保留；未更换API或业务库。当前系统非全功能就绪：QYH自动同步与经营调度仍未恢复。

修正调查中的暂时推断：Docker Desktop的5433/aos_meta虽在运行，但无meta_source表，不是原完整数据库；原卷事故与受保护恢复介质见a0-v-recovery-and-readiness-verification.md。未修改/删除任何事故恢复介质。

SSH配置缺失不再是当前阻断项，旧相关异步问题已由本次主动调查解决。下一波通过正式Source Owner恢复持久配置与探针，不只依赖本轮外置隧道；继续数据同步和自然链路。固定九项调度登记新增访问范围仍单独待答复，不由此次SSH成功替代权限。m1单写者、不push、230 L0挂起。
