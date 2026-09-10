# 向导状态与探针运行位置验证

基线dbd8c677。DataPage增加配置依赖失效effect，修改连接字段/源id/connector/runtime清空旧发现与成功消息；fieldset在提交期间禁用，ref同步拦截双击；SSH端口不再固定。服务器探针检查props.runtimeMode=direct，agent/worker/缺失均拒绝且不连接。前端同样在保存前提示direct限制，不替用户改runtime。

9探针专项通过，覆盖新增三类拒绝；TypeScript初次发现setMsg(null)类型错误，修正为空字符串后全项目--noEmit通过。git diff --check通过。未执行组件交互或本轮浏览器，不能宣称UI状态已实测；代码先于测试扩展，无本轮红阶段证明。旧7警告/JDBC退出问题保持。

该限制明确本机探针范围，agent/worker真实派发仍未实现且属于后续，不以拒绝替代最终多运行时目标。真实连接配置位置仍待回复；完整首链/八工作台未完成。无真实源调用、未重载API、未push，230 L0挂起。
