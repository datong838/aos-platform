# 调度运行身份接续验证

2026-09-11，基线5f66e987。qyh调度claim持久run_id传入execute_pipeline_once/_start_dispatch，再交executor。未指定仍生成pipeline-run UUID；内部输入格式校验后使用。不变更scope/preflight，未新增外部API参数。

实际线程调度2项先红后绿，结合qyh调度测试共12通过，确认指定ID与默认行为、调度错误分类仍保留。DB调度持久化为mock，因此不是实际运行DB连通或源接入证据。diff --check通过，既有7警告与退出日志问题仍在。

下一步journal写前核验持久run的scope/pipeline/running状态及当前source配置，不能只凭字符串认授权。实际executor尚未journal保存；API未重载，完整首链未完成，不push，230 L0挂起。
