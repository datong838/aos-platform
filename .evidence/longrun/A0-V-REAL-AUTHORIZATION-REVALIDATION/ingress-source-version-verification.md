# 源读取版本绑定验证

2026-09-11，基线0ab3df34。新fetch_source_rows_versioned同快照加载连接与配置ref，经类型/状态/direct模式和严格参数校验后独立连接读取；返回清洗rows及实际ref。异常固定SOURCE_VERSIONED_READ_FAILED。原入口未切换，private_connection默认旧行为。

5项先红后绿，加独立连接关闭测试并跑既有两组源适配测试，共21通过；diff --check通过。模拟Owner/传输，不是实际SSH或PG读取；既有7警告/退出日志问题仍在。上游读取保持既有snapshot/增量与清洗语义，没有声称总量完整性或真实新鲜度。

配置可能在读取后变化，后续写前绑定须按返回旧ref拒绝，不重新盖新ref。当前尚未与executor/journal接通，也不证明外部secret material版本。API未重载，无真实源调用，完整首链未完成，不push，230 L0挂起。
