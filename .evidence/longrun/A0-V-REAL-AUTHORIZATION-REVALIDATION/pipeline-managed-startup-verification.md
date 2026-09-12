# 受管启动装配修复

2026-09-13；99b63109。main.py原先把executor/resolver注册置于legacy-bootstrap分支，受管启动没有注册。提取纯内存_register_pipeline_runtime，放到迁移分支后；seed/DDL/计划初始化仍留旧分支。新增AOS_JDBC_SSH_PREBUILD_ENABLED，默认旧行为开启，明确关闭则在源配置读取/连接前返回，后续启动器无需替换函数。

先RED缺注册方法/关闭预热仍调用；修复后注册+受控线程组合20 passed，验证无DB/源调用、旧入口不接受controlled快照、原异常/超时保护。未加载到主API；实际受管启动日志/健康/控制factory验收下一步。新选项只管启动预热，不替代批准计划的正式连接。
