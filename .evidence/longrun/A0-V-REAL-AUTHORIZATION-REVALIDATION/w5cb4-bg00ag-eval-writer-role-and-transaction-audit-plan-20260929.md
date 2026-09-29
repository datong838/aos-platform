# W5CB4 BG-00ag｜正式 Eval writer 身份与事务边界只读审计方案

复习 228 G2.2/231、BG-00z/af 的失败封闭边界和已有 `aip_capability_publisher_connection.py` 独立身份模式。本波只读盘点当前数据库账号可达角色、RLS/ACL、SECURITY DEFINER、Run/Report/Receipt/sidecar 现有权限与事务 Owner；不创建正式账号、不放宽 ACL、不写当前库或执行 Eval。判断是否能在不借 `aos_app` superuser、不借普通 `aos_runtime` 写四表的情况下建立未来同事务 writer，给出下波最小独立配置/代码与验证条件。

验收为精确 SQL/代码路径证据、正负权限矩阵、下一波文件级方案方向，verification/上下文/D-waves 精确提交。正式 issuer/Owner/批准仍以当前资料为准；缺失时生产实例继续禁入。
