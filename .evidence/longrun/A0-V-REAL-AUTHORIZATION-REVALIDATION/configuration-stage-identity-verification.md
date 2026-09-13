# D2d-6 专用登记传输身份验证

2026-09-14，基线84135029，专用租约A0V-CONFIGURATION-STAGE-API-IDENTITY-20260914。

新增脚本复用现有受保护身份读取与configuration_stage_connection。先克隆后主库：唯一NOINHERIT LOGIN aos_configuration_stage_transport_20260914仅继承NOLOGIN aos_configuration_stage_api，可SET ROLE后调用固定函数，未改变任何业务成员、marking或审批。

两库真实连接验证均通过：原runtime-owner和当前安装97a…权限检查通过；不存在原请求ID与key返回NULL；错subject、负租户、直接队列、直接配置表、Host函数5项拒绝。19业务指纹前后一致，队列保持0。身份文件0600，仅私有目录，仓库证明仅记录文件哈希、角色与检查结果。

当前API未加载此身份，原Host未重启、stage开关未打开。身份验证不是登记→绑定→启用成功。下一波UQ6-D2e梳理正式恢复替换产品链路及当前exact审批入口，准备可评审后继安装；保留旧实例，避免先停后无法恢复。
