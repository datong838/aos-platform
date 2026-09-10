# 向导真实配置保存与发现

基线a625f7bc。向导在连接步骤生成会话稳定sourceId，提交仅当前支持jdbc-mysql-ssh字段（端口转数字，不提交空认证字段），保存返回id/version必须合法；GET回读相同版本后POST精确probe，成功才进入表发现。已有保存版本用于后续配置修改CAS。操作中禁止并发按钮；失败停留并保持已保存身份，不自动重试。缺失/漂移响应不伪造id。

移除MOCK_TABLES和假行数；表发现只展示真实表，截断明示。未创建同步任务前不声称表已同步或已持久选表，因此本轮将原假选表呈现改为发现结果与确认；同步配置交给现有入口后续接续。完成只表示保存+探针成功。其他连接器仍显示选择但明确未支持该配置路径，不发送会被丢弃的参数。

文件DataSourceCreatePage.tsx及纯流程helper/test。验证请求字段、顺序、id/version回读、失败不probe；页面构建/浏览器尽可能实测。无真实凭据不宣称真实连接成功。产品整体仍待接入/规范化/首链。

路由复核纠正：旧DataSourceCreatePage未挂载，本轮对该页的自有修改已撤回。实际/data?create=1使用DataPage。实施文件改为DataPage.tsx，复用sourceSetup helper；先在现有创建流程为jdbc-mysql-ssh补SSH字段、配置保存/回读/probe，保持其他metadata流程兼容。成功展示真实发现表，尚未同步；不改历史redirect。原旧页mock不作为当前用户功能，不宣称已移除用户在用页面的mock。先前41 helper/旧页测试不能代替DataPage验收。
