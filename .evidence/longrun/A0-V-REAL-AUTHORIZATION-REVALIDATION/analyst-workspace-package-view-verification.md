# 经营参谋包内 Case/Run 投影验证

基线78ba0fc1。新增领域包纯只读投影，复用包内Case枚举，接受canonical Case/Run/State快照并保留精确refs，输出所需标题、类型、生命周期/control、条数和截断标志，executionAllowed=false。不输出createdBy/triggerKey，不推断业务完成。

20项专项+已有运行协议回归通过，7项既有依赖警告。输入使用现有权威模型生成；验证内容篡改、混租户、重复Case/Run、额外授权字段以及重新计算source hash后的错误Case/State关联均拒绝。首次闭包缺少新文件归属；将文件明确登记为solution包内纯投影后，ar2-7扫描1837/分类162/迁移93，五类错误为空。未改变历史preHash或扫描器规则。

当前旧兼容Case GET真实count=0；没有声称已生成业务案例。本次只改未发布源码模板，已安装1.7.0未改，未将新函数接运行SDK或UI。下一波建立同一截止时间的canonical只读快照端口，并核对当前调用主体；之后通过正式后继包交付接入，才能称实际包内业务读取。
