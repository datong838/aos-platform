# Installed分析启动命令端口

基线4c940d2a，父任务Host/tests。新增 services/aos-api/aos_api/ecommerce_product_event_analysis_port.py 与 tests/extension_runtime/test_product_event_analysis_port.py。

精确CurrentInstalledPackageInvoker，固定solution.ecommerce.growth、analysis_advance、build_analysis_start。仅调用一次，不直接import领域包。严格请求身份与UTC秒；返回命令用已有Host START解析/哈希验证，逐字段对应输入并要求START/prior空；返回隔离副本。Invoker负责当前安装前后复核，本端口不创建Run或授予权限。超时传播不重试。

测试替身明确仅验证编排，不算真实OCI。错包、错引用、错key/时间、篡改哈希、返回resume/extra、超时、输入突变均拒绝或隔离。随后串联claim与当前事件控制权限、Host写事务。
