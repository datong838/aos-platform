# 当前恢复库升级与诊断服务重载

2026-09-11，代码1100b936，迁移3afa2303；沿既有全权本地开发授权，m1串行、不push、230 L0挂起。

显式数据库colima-aos-extension/aos-a0v-recovery-pg/aos_meta_head；升级前版本a0v001、512表，另建4523083字节备份，SHA256 3c62d754765f7ae814743ebc612c7c67f219c7400383e7f1aba3639b9d2cd444。路径/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/upgrade-checks/actual_51beb87a8a4a/before-upgrade.dump，目录0700/文件0600、不提交客户备份。

Alembic完整001→011成功，锁等待5秒/语句60秒；没有强制清锁、终止数据库连接或改其他库。升级后518表，原512表逐表行数一致；executor_stopped默认false NOT NULL；原Journal/claim强制RLS。已在前波证明历史备份兼容恢复及修复后新备份直接恢复，不对forward-only安全迁移执行降级。

原诊断API PID17113经准确脚本身份核对后SIGTERM；同脚本重启PID38300，会话13353，18181加载1100b936。保留迁移disabled/QYH cron false/AIP automation false/text health false/extension host 0/SSH预建禁用。disabled不执行legacy bootstrap种子流程。

HTTP：/openapi.json 200且恢复路由存在；/v1/schedules 200 items0；/v1/ecommerce/investigations/cases 200 items0；case-selection首次分析200，CANONICAL_SHOP_SELECTION_UNAVAILABLE/SOURCE_READINESS_NOT_READY；source-readiness404 WORKSHOP_NOT_INSTALLED。/health404（不是该服务健康端点），不能报健康检查通过。重载和这些读取后原512表行数仍一致。

IAB实际打开8434/workshop/analyst，加载后显示“模块未安装／当前工作区的active installation中没有此模块”，只做页面读取，未创建计划或触发模型。表示缺少有效安装，不证明没有历史/已批准安装。

结论：数据库和诊断服务已追上当前恢复代码，安装、数据和业务链仍未就绪。下一波读取既有canonical first-install状态及当前运行配置，恢复有效安装路径；同时保持首次经营分析和自然事件接线清单，不能只填一份空壳业务计划。真实首链/八场景/观察/发布尚未完成。
