# 实际DataPage组件交互验证

基线7c601fa1。本轮用React DOM挂载DataPage，模拟API及页面外框，经过真实按钮/输入走已安装JDBC SSH→direct→SSH/数据库参数→凭据→保存→版本回读→精确探针。成功用延迟Promise观察fieldset disabled，完成显示ns_goods合成表和未同步说明；返回修改数据库名后旧发现结果消失。另一分支回读版本漂移只发生save/readback，不调用probe，表单恢复并显示失败。

运行DataPage.source.interaction、sourceSetup、Wave3bW4Truth共19 passed；git diff --check通过。没有产品代码修改。本次不是浏览器真实HTTP或上游连接验收，也没有模拟真实客户数据。已有React Router future flag警告保留。未测试未知提交恢复、真正双击事件或页面卸载中的请求取消，不扩大结论。

下一步实际HTTP/PG配置版本历史及probe权限/锁组合，API需安全重载后再验证新路由；缺失原真实配置位置仍待回复。首链/八工作台/连续观察未完成，无push，230 L0挂起。
