# 实际DataPage组件交互验证

基线7c601fa1。用React DOM挂载实际/DataPage并模拟现有API，走真实按钮和输入：已安装JDBC SSH→direct→SSH/DB字段→凭据→保存→GET回读→精确probe。延迟probe验证fieldset禁用/重复提交不发生，完成显示真实测试表，返回修改参数清除结果。验证发送端口数字及无空认证字段、未知回读不触发probe。模拟API不证明真实网络，后续HTTP/PG/上游继续。

新增apps/web/src/pages/DataPage.source.interaction.test.tsx；仅实际复现缺陷时修改产品代码。无真实凭据或数据库写入。
