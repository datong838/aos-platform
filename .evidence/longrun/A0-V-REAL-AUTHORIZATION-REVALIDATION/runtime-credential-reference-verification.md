# 运行身份文件引用验证

2026-09-12，基线bb737f14。runtime_worker_connection新增可选AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE：绝对路径、O_NOFOLLOW、普通文件、自有uid、0600、最大64KiB，固定三平面结构；读取后只在内存使用DSN，与web身份不同。坏引用失败，不回退环境URL；未提供文件引用时保持旧URL兼容。新预检脚本只设置引用路径与非秘密包配置，不复制凭据到环境。

5项新增RED后实现，旧连接与工厂共12项通过。10:43:12Z真实文件引用预检currentChecksPassed=true，零审批/源行/业务写入；证据pipeline-control-credential-reference-preflight.json。原Host未重启，身份、角色成员关系和权限未变。

项目强投影CURRENT、validate GREEN。新增两项独占m1任务登记：A0V-PIPELINE-CONTROL-LOCAL-MIGRATION-20260912（仅本地恢复库a0v_021→023）、A0V-PIPELINE-CONTROL-RESTORE-DRILL-20260912（仅命名隔离克隆恢复验证），均至09-13 23:59。尚未执行备份/克隆/迁移，此提交只完成凭据引用及部署准备；后续按pipeline-control-deployment-plan.md继续。不push、230 L0挂起。
