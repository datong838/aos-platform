# SC4-1 当前编译输入组装验证

基线a53d683d，m1父Lease内修改ecommerce_analysis_compilation_binding.py，新增test_analysis_compilation_preparation.py。L1保持领域意图，L2按租户、Run及安装依赖内容寻址；按蓝图顺序组装三阶段已选择Skill、首阶段Logic入口、SkillBindingSet、职责、阶段模板、本任务Brief和Context，返回严格AnalysisCompilationBinding。函数只检查已准备合同间一致性，不是实时数据库权威或运行授权；SC4-2必须在当前Context回调内调用并执行真实exact解析/Saga。

RED：16项因尚无入口ImportError失败。GREEN：修正fixture引用多余空receiptId后33 passed；累计原编译器、Saga、Binding和真实PG Context为41 passed（7.32s）。乱序读取不改变结果；Context跨Task/Brief/职责、hash漂移、角色跨租户、模板内容/profile、技能Logic/hash/缺漏/重复、安装代际、bindingRef、Task目标和蓝图错接均拒绝。

AR2 ar2-7 1898/176/93，全部错误列表为空；memoryctl validate GREEN AOS-000573；git diff --check通过。组装单测使用明示合同fixture；累计Context测试的真实PG边界与SC3-2一致，不宣称正式START/运行完成。下一SC4-2真实exact解析器+CompileSaga，之后TaskRun与sealed Host；主安装、首链、八场景和观察未完成。不push，230 L0挂起。
